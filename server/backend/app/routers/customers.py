"""客户路由。

读端点 100 req/min/IP，写端点 30 req/min/IP（project_memory 硬约束：
stricter for write endpoints）。

错误语义对齐 expenses/mail_record/aftersales/warranty：客户不存在返回 404，
业务校验失败（昵称重复/为空/有未删除交易）返回 400，乐观锁冲突返回 409。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import CustomerCreate, CustomerUpdate, CustomerOut
from ..security import limiter
from ..services import customer_service
from ..services.customer_service import CustomerError, CustomerNotFoundError
from ..utils.helpers import ConcurrencyError

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
@limiter.limit("100/minute")
async def list_customers(
    request: Request,
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
@limiter.limit("100/minute")
async def get_customer(request: Request, customer_id: int, db: AsyncSession = Depends(get_db)):
    c = await customer_service.get_customer(db, customer_id)
    if c is None:
        raise HTTPException(404, "客户不存在")
    await db.commit()
    return c


@router.post("", response_model=CustomerOut)
@limiter.limit("30/minute")
async def create_customer(
    request: Request,
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
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
@limiter.limit("30/minute")
async def update_customer(
    request: Request,
    customer_id: int,
    payload: CustomerUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    expected_version = data.pop("expected_version", None)
    try:
        c = await customer_service.update_customer(db, customer_id, data, expected_version)
        await db.commit()
        return c
    except ConcurrencyError as e:
        raise HTTPException(409, str(e))
    except CustomerNotFoundError as e:
        raise HTTPException(404, str(e))
    except CustomerError as e:
        raise HTTPException(400, str(e))


@router.delete("/{customer_id}")
@limiter.limit("30/minute")
async def delete_customer(
    request: Request,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await customer_service.soft_delete_customer(db, customer_id)
        await db.commit()
        return {"message": "已删除"}
    except CustomerNotFoundError as e:
        raise HTTPException(404, str(e))
    except CustomerError as e:
        raise HTTPException(400, str(e))


@router.post("/{customer_id}/toggle-blacklist", response_model=CustomerOut)
@limiter.limit("30/minute")
async def toggle_blacklist(
    request: Request,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        c = await customer_service.toggle_blacklist(db, customer_id)
        await db.commit()
        return c
    except CustomerNotFoundError as e:
        raise HTTPException(404, str(e))
    except CustomerError as e:
        raise HTTPException(400, str(e))
