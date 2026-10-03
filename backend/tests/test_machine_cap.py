"""整机补货件数上限：截断口径、原因文案、上限编辑与落单一致性。"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.locations import LocationUpdate, update_location
from app.database import Base
from app.models.models import Location
from app.services.fill_engine import plan_refill
from app.services.refill_service import generate_refill
from app.services.seed import seed_if_empty


def _lanes():
    return [
        {"id": 1, "slot_no": "A1", "sku_name": "矿泉水", "capacity": 20, "stock": 5, "in_transit": 0},  # 缺 15
        {"id": 2, "slot_no": "B1", "sku_name": "薯片", "capacity": 12, "stock": 3, "in_transit": 2},    # 缺 7
        {"id": 3, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 0, "in_transit": 0},  # 缺 10
    ]


SALES = {3: 6, 2: 4, 1: 2}  # 近七日销量 C1 > B1 > A1


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_cap_distributed_by_sales_desc():
    s = plan_refill(_lanes(), max_total=20, sales_7d=SALES)
    by_id = {l["lane_id"]: l for l in s["lines"]}
    assert by_id[3]["fill_qty"] == 10  # 高销量先吃满
    assert by_id[2]["fill_qty"] == 7
    assert by_id[1]["fill_qty"] == 3   # 低销量只分到剩余额度
    assert s["total_fill"] == 20
    assert s["total_fill"] == sum(l["fill_qty"] for l in s["lines"])


def test_cap_exhausted_lane_zero_with_capped_reason():
    s = plan_refill(_lanes(), max_total=17, sales_7d=SALES)  # 10 + 7 分满，A1 截为 0
    by_id = {l["lane_id"]: l for l in s["lines"]}
    assert by_id[1]["fill_qty"] == 0
    assert by_id[1]["status"] == "capped"
    assert by_id[1]["reason"] == "整机件数已满"
    assert s["capped_count"] == 1
    assert s["total_fill"] == 17


def test_capped_reason_not_merged_with_full_or_overbooked():
    lanes = _lanes() + [
        {"id": 4, "slot_no": "D1", "sku_name": "可乐", "capacity": 10, "stock": 10, "in_transit": 0},   # 满仓
        {"id": 5, "slot_no": "E1", "sku_name": "口香糖", "capacity": 10, "stock": 12, "in_transit": 0},  # 超占
    ]
    s = plan_refill(lanes, max_total=17, sales_7d=SALES)
    by_id = {l["lane_id"]: l for l in s["lines"]}
    assert by_id[1]["status"] == "capped" and by_id[1]["reason"] == "整机件数已满"
    assert by_id[4]["status"] == "full" and by_id[4]["reason"] == "单道已满仓"
    assert by_id[5]["status"] == "overbooked" and by_id[5]["reason"] == "单道超占"


def test_cap_zero_means_unlimited():
    s = plan_refill(_lanes(), max_total=0, sales_7d=SALES)
    assert s["total_fill"] == 15 + 7 + 10
    assert all(l["status"] == "need_fill" for l in s["lines"])


def test_total_never_exceeds_cap():
    for cap in (1, 5, 9, 20, 100):
        s = plan_refill(_lanes(), max_total=cap, sales_7d=SALES)
        assert s["total_fill"] <= cap
        assert s["total_fill"] == sum(l["fill_qty"] for l in s["lines"])


def test_seed_cap20_summary_matches_order_lines():
    db = _session()
    seed_if_empty(db)
    result = generate_refill(db, 1)
    assert result["max_fill_total"] == 20
    assert result["total_fill"] == 20
    assert result["total_fill"] == sum(l["fill_qty"] for l in result["lines"])
    by_slot = {l["slot_no"]: l for l in result["lines"]}
    assert by_slot["C1"]["fill_qty"] == 10  # 销量 6 最高
    assert by_slot["B1"]["fill_qty"] == 7   # 销量 4
    assert by_slot["A1"]["fill_qty"] == 3   # 销量 2，只分到剩余 3 件
    db.close()


def test_total_fill_capped_below_cap_when_gap_insufficient():
    db = _session()
    seed_if_empty(db)
    update_location(1, LocationUpdate(max_fill_total=100), db)  # 上限大于全机缺口 32
    result = generate_refill(db, 1)
    assert result["total_fill"] == 32 < 100
    db.close()


def test_negative_cap_rejected_and_nothing_changes():
    db = _session()
    seed_if_empty(db)
    before = generate_refill(db, 1)["total_fill"]
    with pytest.raises(HTTPException):
        update_location(1, LocationUpdate(max_fill_total=-5), db)
    assert db.get(Location, 1).max_fill_total == 20  # 点位保持改前
    assert generate_refill(db, 1)["total_fill"] == before  # 补货单/汇总保持改前
    db.close()


def test_next_run_uses_newly_saved_cap():
    db = _session()
    seed_if_empty(db)
    update_location(1, LocationUpdate(max_fill_total=12), db)
    result = generate_refill(db, 1)
    assert result["max_fill_total"] == 12
    assert result["total_fill"] == 12
    update_location(1, LocationUpdate(max_fill_total=0), db)  # 0 = 不限制
    assert generate_refill(db, 1)["total_fill"] == 32
    db.close()


def test_cap_persists_across_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db1 = Session()
    seed_if_empty(db1)
    update_location(1, LocationUpdate(max_fill_total=8), db1)
    db1.close()
    db2 = Session()  # 离开再进仍是新值
    assert db2.get(Location, 1).max_fill_total == 8
    db2.close()
