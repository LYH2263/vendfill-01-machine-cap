import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane, Location, RefillOrder, Sale
from app.services.fill_engine import build_fill_lines, summarize
router = APIRouter(prefix="/refills", tags=["refills"])

def _sales_last_7d(db: Session, lane_ids: list[int]) -> dict[int, int]:
    """近七日各货道销量，作为整机上限截断时的分配优先级。"""
    if not lane_ids:
        return {}
    since = datetime.utcnow() - timedelta(days=7)
    rows = db.execute(
        select(Sale.lane_id, func.coalesce(func.sum(Sale.qty), 0))
        .where(Sale.lane_id.in_(lane_ids), Sale.sold_at >= since)
        .group_by(Sale.lane_id)
    ).all()
    return {lane_id: int(qty) for lane_id, qty in rows}

def run_refill(location_id: int, db: Session) -> dict:
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    # 以保存当下读到的上限为准重算，绝不沿用上一张单的总分。
    max_fill_qty = int(loc.max_fill_qty or 0)
    lanes = db.scalars(select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    sold_7d = _sales_last_7d(db, [l.id for l in lanes])
    # 补货单、汇总、满仓页共用这一份截断结果。
    summary = summarize(build_fill_lines(payload, max_fill_qty=max_fill_qty, sold_7d=sold_7d),
                        max_fill_qty=max_fill_qty)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}

@router.post("/run")
def run(location_id: int = 1, db: Session = Depends(get_db)):
    return run_refill(location_id=location_id, db=db)

@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                       .order_by(RefillOrder.id.desc())).first()
    if not order:
        return run_refill(location_id=location_id, db=db)
    data = json.loads(order.lines_json)
    return {"id": order.id, "location_id": location_id, **data}

@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    # 仅单道缺口为 0 的满仓道；被整机上限截成 0 的货道不在这里（原因不同）。
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
        "capped_count": data.get("capped_count", 0),
        "max_fill_qty": data.get("max_fill_qty", 0),
    }
