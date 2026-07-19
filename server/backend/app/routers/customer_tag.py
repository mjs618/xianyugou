"""客户标签路由。

读端点 100 req/min/IP，写端点 30 req/min/IP（project_memory 硬约束：
stricter for write endpoints）。

错误语义对齐 expenses/mail_record/aftersales/warranty：
- 资源不存在（标签或客户）返回 404
- 业务校验失败（标签名重复/为空）返回 400
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CustomerTagCreate, CustomerTagsUpdate
from ..security import limiter
from ..services import customer_tag_service
from ..services.customer_tag_service import TagError, TagNotFoundError

router = APIRouter(prefix="/api/customer-tags", tags=["customer-tags"])


def _to_dict(t) -> dict:
    return {
        "id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
@limiter.limit("100/minute")
async def list_tags(request: Request, db: AsyncSession = Depends(get_db)):
    items = await customer_tag_service.list_tags(db)
    await db.commit()
    return [_to_dict(t) for t in items]


@router.get("/by-customer/{customer_id}")
@limiter.limit("100/minute")
async def tags_by_customer(request: Request, customer_id: int, db: AsyncSession = Depends(get_db)):
    items = await customer_tag_service.get_customer_tags(db, customer_id)
    await db.commit()
    return [_to_dict(t) for t in items]


@router.post("")
@limiter.limit("30/minute")
async def create_tag(
    request: Request,
    payload: CustomerTagCreate = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await customer_tag_service.create_tag(db, payload.name, payload.color)
        await db.commit()
        return _to_dict(t)
    except TagError as e:
        raise HTTPException(400, str(e))


@router.post("/set-customer/{customer_id}")
@limiter.limit("30/minute")
async def set_customer_tags(
    request: Request,
    customer_id: int,
    payload: CustomerTagsUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        await customer_tag_service.set_customer_tags(db, customer_id, payload.tags)
        await db.commit()
        return {"ok": True}
    except TagNotFoundError as e:
        raise HTTPException(404, str(e))
    except TagError as e:
        raise HTTPException(400, str(e))


@router.delete("/{tag_id}")
@limiter.limit("30/minute")
async def delete_tag(request: Request, tag_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await customer_tag_service.delete_tag(db, tag_id)
        await db.commit()
        return {"ok": True}
    except TagNotFoundError as e:
        raise HTTPException(404, str(e))
