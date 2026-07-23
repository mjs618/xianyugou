"""交易路由

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/transactions → 100/minute（读端点）
- GET /api/transactions/{tx_id} → 100/minute（读端点）
- POST /api/transactions → 30/minute（写端点）
- PATCH /api/transactions/{tx_id} → 30/minute（写端点）
- DELETE /api/transactions/{tx_id} → 30/minute（写端点）
- POST /api/transactions/{tx_id}/status → 30/minute（写端点）
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    TransactionCreate, TransactionUpdate, TransactionOut, StatusChange,
)
from ..security import limiter
from ..services import transaction_service
from ..services.transaction_service import TransactionError, TransactionNotFoundError
from ..utils.helpers import ConcurrencyError

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
@limiter.limit("100/minute")
async def list_transactions(
    request: Request,
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="起始日期 ISO"),
    end: Optional[str] = Query(None, description="结束日期 ISO"),
    channel: Optional[str] = Query(None, description="销售渠道过滤：xianyu/wechat/other"),
    with_name: bool = Query(False, description="是否内联返回 customer_name"),
    db: AsyncSession = Depends(get_db),
):
    from ..utils.helpers import parse_date
    start_dt = parse_date(start) if start else None
    end_dt = parse_date(end) if end else None
    items = await transaction_service.list_transactions(
        db, customer_id=customer_id, status=status, start=start_dt, end=end_dt,
        channel=channel, with_customer_name=with_name,
    )
    await db.commit()
    return items


@router.get("/{tx_id}", response_model=TransactionOut)
@limiter.limit("100/minute")
async def get_transaction(
    request: Request, tx_id: int, db: AsyncSession = Depends(get_db)
):
    t = await transaction_service.get_transaction(db, tx_id)
    if t is None:
        raise HTTPException(404, "交易不存在")
    await db.commit()
    return t


@router.post("", response_model=TransactionOut)
@limiter.limit("30/minute")
async def create_transaction(
    request: Request,
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await transaction_service.create_transaction(
            db,
            customer_id=payload.customer_id,
            product_name=payload.product_name,
            sale_price=payload.sale_price,
            cost_price=payload.cost_price,
            trade_at=payload.trade_at,
            shipped_at=payload.shipped_at,
            status=payload.status,
            warranty_days=payload.warranty_days,
            source_type=payload.source_type,
            channel=payload.channel,
            xianyu_order_no=payload.xianyu_order_no,
            product_template_id=payload.product_template_id,
            source_customer_id=payload.source_customer_id,
            notes=payload.notes,
            attachments=payload.attachments,
        )
        await db.commit()
        return t
    except TransactionError as e:
        raise HTTPException(400, str(e))


@router.patch("/{tx_id}", response_model=TransactionOut)
@limiter.limit("30/minute")
async def update_transaction(
    request: Request,
    tx_id: int,
    payload: TransactionUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    expected_version = data.pop("expected_version", None)
    try:
        t = await transaction_service.update_transaction(db, tx_id, data, expected_version)
        await db.commit()
        return t
    except ConcurrencyError as e:
        raise HTTPException(409, str(e))
    except TransactionNotFoundError as e:
        raise HTTPException(404, str(e))
    except TransactionError as e:
        raise HTTPException(400, str(e))


@router.delete("/{tx_id}")
@limiter.limit("30/minute")
async def delete_transaction(
    request: Request, tx_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        await transaction_service.soft_delete_transaction(db, tx_id)
        await db.commit()
        return {"message": "已删除"}
    except TransactionNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/{tx_id}/status", response_model=TransactionOut)
@limiter.limit("30/minute")
async def change_status(
    request: Request,
    tx_id: int,
    payload: StatusChange = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await transaction_service.change_status(db, tx_id, payload.status, payload.expected_version)
        await db.commit()
        return t
    except ConcurrencyError as e:
        raise HTTPException(409, str(e))
    except TransactionNotFoundError as e:
        raise HTTPException(404, str(e))
    except TransactionError as e:
        raise HTTPException(400, str(e))
