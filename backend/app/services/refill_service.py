"""Single refill-generation path shared by the API and tests, so the refill
order, summary and location pages always see the same truncation result."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Lane, Location, RefillOrder, Sale
from app.services.fill_engine import plan_refill

SALES_WINDOW_DAYS = 7


def sales_7d_by_lane(db: Session, location_id: int) -> dict[int, int]:
    """近七日销量 per lane for one location."""
    since = datetime.utcnow() - timedelta(days=SALES_WINDOW_DAYS)
    rows = db.execute(
        select(Sale.lane_id, func.coalesce(func.sum(Sale.qty), 0))
        .join(Lane, Lane.id == Sale.lane_id)
        .where(Lane.location_id == location_id, Sale.sold_at >= since)
        .group_by(Sale.lane_id)
    ).all()
    return {int(lane_id): int(total) for lane_id, total in rows}


def generate_refill(db: Session, location_id: int) -> dict:
    """Compute the refill plan with the location's currently saved cap, persist
    it as a new order, and return the order payload."""
    loc = db.get(Location, location_id)
    if loc is None:
        raise LookupError("点位不存在")
    lanes = db.scalars(select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    # 按保存当下读到的上限重算：每次落单都重新读取点位上限
    max_total = int(loc.max_fill_total or 0)
    summary = plan_refill(payload, max_total=max_total, sales_7d=sales_7d_by_lane(db, location_id))
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}
