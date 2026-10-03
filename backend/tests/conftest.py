import os
import tempfile
from datetime import datetime, timedelta

# 必须在导入应用代码前指定 sqlite 测试库
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import Lane, Location, Sale


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def make_location(max_fill_qty: int) -> int:
    """插入与种子同构的点位，返回其 id。"""
    db = SessionLocal()
    try:
        loc = Location(code="VM-T", name="测试点", address="x", max_fill_qty=max_fill_qty)
        db.add(loc); db.flush()
        rows = [
            ("A1", "矿泉水", 20, 5, 0),    # 缺口 15, 销量 2
            ("A2", "可乐", 18, 18, 0),     # 满仓
            ("B1", "薯片", 15, 3, 2),      # 缺口 10, 销量 4
            ("B2", "巧克力", 15, 10, 5),   # 满仓
            ("C1", "能量棒", 10, 0, 0),    # 缺口 10, 销量 6
            ("C2", "口香糖", 24, 24, 2),   # 超占
        ]
        now = datetime.utcnow()
        for i, (slot, sku, cap, stock, transit) in enumerate(rows):
            lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                        capacity=cap, stock=stock, in_transit=transit)
            db.add(lane); db.flush()
            db.add(Sale(lane_id=lane.id, qty=2 + i, sold_at=now - timedelta(hours=i)))
        db.commit()
        return loc.id
    finally:
        db.close()
