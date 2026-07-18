"""售后工单路由。

读端点 100 req/min/IP，写端点 30 req/min/IP（project_memory 硬约束：
stricter for write endpoints）。

错误语义对齐 expenses/mail_record：资源不存在返回 404，业务校验失败返回 400。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import AfterSalesCreate, AfterSalesUpdate, AfterSalesOut
from ..security import limiter
from ..services import aftersales_service
from ..services.aftersales_service import AfterSalesError, AfterSalesNotFoundError

router = APIRouter(prefix="/api/aftersales", tags=["aftersales"])


@router.get("", response_model=list[AfterSalesOut])
@limiter.limit("100/minute")
async def list_aftersales(request: Request, db: AsyncSession = Depends(get_db)):
    items = await aftersales_service.list_aftersales(db)
    await db.commit()
    return items


@router.get("/by-transaction/{tx_id}", response_model=list[AfterSalesOut])
@limiter.limit("100/minute")
async def by_transaction(request: Request, tx_id: int, db: AsyncSession = Depends(get_db)):
    items = await aftersales_service.list_by_transaction(db, tx_id)
    await db.commit()
    return items


@router.get("/stats")
@limiter.limit("100/minute")
async def stats(request: Request, db: AsyncSession = Depends(get_db)):
    data = await aftersales_service.get_after_sales_stats(db)
    await db.commit()
    return data


@router.get("/top-issues")
@limiter.limit("100/minute")
async def top_issues(request: Request, limit: int = 10, db: AsyncSession = Depends(get_db)):
    # 限制 limit 范围，避免恶意拉取全表
    if limit < 1:
        limit = 1
    elif limit > 100:
        limit = 100
    data = await aftersales_service.get_top_issue_products(db, limit)
    await db.commit()
    return data


@router.get("/{ticket_id}", response_model=AfterSalesOut)
@limiter.limit("100/minute")
async def get_aftersales(request: Request, ticket_id: int, db: AsyncSession = Depends(get_db)):
    a = await aftersales_service.get_aftersales(db, ticket_id)
    if a is None:
        raise HTTPException(404, "工单不存在")
    await db.commit()
    return a


@router.post("", response_model=AfterSalesOut)
@limiter.limit("30/minute")
async def create_aftersales(
    request: Request,
    payload: AfterSalesCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        a = await aftersales_service.create_aftersales(
            db,
            transaction_id=payload.transaction_id,
            issue_desc=payload.issue_desc,
            attachments=payload.attachments,
        )
        await db.commit()
        return a
    except AfterSalesNotFoundError as e:
        raise HTTPException(404, str(e))
    except AfterSalesError as e:
        raise HTTPException(400, str(e))


@router.patch("/{ticket_id}", response_model=AfterSalesOut)
@limiter.limit("30/minute")
async def update_aftersales(
    request: Request,
    ticket_id: int,
    payload: AfterSalesUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        a = await aftersales_service.update_status(
            db, ticket_id, payload.status, payload.solution_type, payload.solution_desc
        )
        await db.commit()
        return a
    except AfterSalesNotFoundError as e:
        raise HTTPException(404, str(e))
    except AfterSalesError as e:
        raise HTTPException(400, str(e))


@router.delete("/{ticket_id}")
@limiter.limit("30/minute")
async def delete_aftersales(
    request: Request,
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        await aftersales_service.delete_aftersales(db, ticket_id)
        await db.commit()
        return {"message": "已删除"}
    except AfterSalesNotFoundError as e:
        raise HTTPException(404, str(e))
    except AfterSalesError as e:
        raise HTTPException(400, str(e))
