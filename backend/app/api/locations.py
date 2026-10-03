from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Location
router = APIRouter(prefix="/locations", tags=["locations"])

class LocationPatch(BaseModel):
    # 整机一次补货最大总件数；0=不限制，负数拒绝
    max_fill_qty: int

@router.get("")
def list_locations(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name": r.name, "address": r.address,
             "max_fill_qty": r.max_fill_qty}
            for r in db.scalars(select(Location).order_by(Location.id)).all()]

@router.patch("/{location_id}")
def update_location(location_id: int, body: LocationPatch, db: Session = Depends(get_db)):
    # 先校验再写入：负数直接 400，点位页/补货单/汇总全部保持改前，杜绝半成功。
    if body.max_fill_qty < 0:
        raise HTTPException(400, "整机补货上限不能为负数")
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    loc.max_fill_qty = body.max_fill_qty
    db.commit(); db.refresh(loc)
    return {"id": loc.id, "code": loc.code, "name": loc.name, "address": loc.address,
            "max_fill_qty": loc.max_fill_qty}
