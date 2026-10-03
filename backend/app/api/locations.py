from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Location
router = APIRouter(prefix="/locations", tags=["locations"])

class LocationUpdate(BaseModel):
    max_fill_total: int

def _to_dict(r: Location) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "address": r.address,
            "max_fill_total": r.max_fill_total}

@router.get("")
def list_locations(db: Session = Depends(get_db)):
    return [_to_dict(r) for r in db.scalars(select(Location).order_by(Location.id)).all()]

@router.put("/{location_id}")
def update_location(location_id: int, body: LocationUpdate, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    # 负数上限整体拒绝保存：点位页、补货单、汇总全部保持改前
    if body.max_fill_total < 0:
        raise HTTPException(400, "整机补货件数上限不能为负数")
    loc.max_fill_total = body.max_fill_total
    db.commit(); db.refresh(loc)
    return _to_dict(loc)
