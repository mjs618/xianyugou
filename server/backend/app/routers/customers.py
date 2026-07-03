"""客户路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CustomerCreate, CustomerUpdate, CustomerOut
from ..services import customer_service
from ..services.customer_service import CustomerError
from ..utils.helpers import ConcurrencyError

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if keyword:
        items = await customer_service.search_customers(db, keyword)
    else:
        items = await customer_service.list_customers(db)
    await db.commit()
    return items


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    c = await customer_service.get_customer(db, customer_id)
    if c is None:
        raise HTTPException(404, "客户不存在")
    await db.commit()
    return c


@router.post("", response_model=CustomerOut)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    try:
        c = await customer_service.create_customer(
            db,
            xianyu_nickname=payload.xianyu_nickname,
            contact_info=payload.contact_info,
            notes=payload.notes,
            is_blacklist=payload.is_blacklist,
        )
        await db.commit()
        return c
    except CustomerError as e:
        raise HTTPException(400, str(e))


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: int, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    expected_version = payload.pop("expected_version", None)
    try:
        c = await customer_service.update_customer(db, customer_id, payload, expected_version)
        await db.commit()
        return c
    except ConcurrencyError as e:
        raise HTTPException(409, str(e))
    except CustomerError as e:
        raise HTTPException(400, str(e))


@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await customer_service.soft_delete_customer(db, customer_id)
        await db.commit()
        return {"message": "已删除"}
    except CustomerError as e:
        raise HTTPException(400, str(e))


@router.post("/{customer_id}/toggle-blacklist", response_model=CustomerOut)
async def toggle_blacklist(customer_id: int, db: AsyncSession = Depends(get_db)):
    try:
        c = await customer_service.toggle_blacklist(db, customer_id)
        await db.commit()
        return c
    except CustomerError as e:
        raise HTTPException(400, str(e))
