import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import RefillOrder
from app.services.refill_service import generate_refill
router = APIRouter(prefix="/refills", tags=["refills"])

@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    try:
        return generate_refill(db, location_id)
    except LookupError:
        raise HTTPException(404, "点位不存在")

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
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "max_fill_total": data.get("max_fill_total", 0),
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
        "capped_count": data.get("capped_count", 0),
    }
