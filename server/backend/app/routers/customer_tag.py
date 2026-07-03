"""客户标签路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import customer_tag_service
from ..services.customer_tag_service import TagError

router = APIRouter(prefix="/api/customer-tags", tags=["customer-tags"])


def _to_dict(t) -> dict:
    return {
        "id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
async def list_tags(db: AsyncSession = Depends(get_db)):
    items = await customer_tag_service.list_tags(db)
    await db.commit()
    return [_to_dict(t) for t in items]


@router.get("/by-customer/{customer_id}")
async def tags_by_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    items = await customer_tag_service.get_customer_tags(db, customer_id)
    await db.commit()
    return [_to_dict(t) for t in items]


@router.post("")
async def create_tag(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    name = payload.get("name", "")
    color = payload.get("color")
    try:
        t = await customer_tag_service.create_tag(db, name, color)
        await db.commit()
        return _to_dict(t)
    except TagError as e:
        raise HTTPException(400, str(e))


@router.post("/set-customer/{customer_id}")
async def set_customer_tags(customer_id: int, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    tag_names = payload.get("tags", [])
    try:
        await customer_tag_service.set_customer_tags(db, customer_id, tag_names)
        await db.commit()
        return {"ok": True}
    except TagError as e:
        raise HTTPException(400, str(e))


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    await customer_tag_service.delete_tag(db, tag_id)
    await db.commit()
    return {"ok": True}
