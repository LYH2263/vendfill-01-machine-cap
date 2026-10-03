from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Lane, Location, Sale

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Location)) or 0) > 0:
        return
    # 整机一次补货上限 20 件；0 才是不限制。
    loc = Location(code="VM-01", name="地铁口 A 点位", address="城东地铁 1 号口", max_fill_qty=20)
    db.add(loc); db.flush()
    lanes = [
        ("A1", "矿泉水", 20, 5, 0),    # 缺口15，近7日销量最低
        ("A2", "可乐", 18, 18, 0),     # 满仓
        ("B1", "薯片", 15, 3, 2),      # 缺口10
        ("B2", "巧克力", 15, 10, 5),   # 满仓
        ("C1", "能量棒", 10, 0, 0),    # 缺口10，近7日销量最高
        ("C2", "口香糖", 24, 24, 2),   # 超占
    ]
    lane_ids = []
    for slot, sku, cap, stock, transit in lanes:
        lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku, capacity=cap, stock=stock, in_transit=transit)
        db.add(lane); db.flush()
        lane_ids.append(lane.id)
    # 销量落在近七日内，作为上限截断的分配依据：高销量道先吃满。
    now = datetime.utcnow()
    for i, lid in enumerate(lane_ids):
        db.add(Sale(lane_id=lid, qty=2 + i, sold_at=now - timedelta(hours=i)))
    db.commit()
