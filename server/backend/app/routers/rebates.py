"""返利路由

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- 4 GET（list/pending-count/pending-total/by-referrer/by-transaction）→ 100/minute（读端点）
- PATCH /{rebate_id} → 30/minute（写端点，状态变更）
- POST /batch-pay → 30/minute（写端点，批量结算）

404 语义：mark_paid/cancel_rebate 不存在抛 RebateNotFoundError → 404，
状态转换错误抛 RebateError → 400（对齐 aftersales/warranty/customers）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import RebateStatusChange, RebateBatchPay, RebateOut
from ..security import limiter
from ..services import rebate_service
from ..services.rebate_service import RebateError, RebateNotFoundError

router = APIRouter(prefix="/api/rebates", tags=["rebates"])


@router.get("", response_model=list[RebateOut])
@limiter.limit("100/minute")
async def list_rebates(request: Request, db: AsyncSession = Depends(get_db)):
    items = await rebate_service.list_rebates(db)
    await db.commit()
    return items


@router.get("/pending-count")
@limiter.limit("100/minute")
async def pending_count(request: Request, db: AsyncSession = Depends(get_db)):
    count = await rebate_service.get_pending_count(db)
    await db.commit()
    return {"count": count}


@router.get("/pending-total")
@limiter.limit("100/minute")
async def pending_total(request: Request, db: AsyncSession = Depends(get_db)):
    total = await rebate_service.get_pending_total(db)
    await db.commit()
    return {"total": total}


@router.get("/by-referrer/{referrer_id}", response_model=list[RebateOut])
@limiter.limit("100/minute")
async def by_referrer(request: Request, referrer_id: int, db: AsyncSession = Depends(get_db)):
    items = await rebate_service.list_by_referrer(db, referrer_id)
    await db.commit()
    return items


@router.get("/by-transaction/{tx_id}")
@limiter.limit("100/minute")
async def by_transaction(request: Request, tx_id: int, db: AsyncSession = Depends(get_db)):
    r = await rebate_service.get_rebate_by_transaction(db, tx_id)
    await db.commit()
    return r


@router.patch("/{rebate_id}")
@limiter.limit("30/minute")
async def update_rebate_status(
    request: Request,
    rebate_id: int,
    payload: RebateStatusChange,
    db: AsyncSession = Depends(get_db),
):
    try:
        if payload.status == "paid":
            r = await rebate_service.mark_paid(db, rebate_id, payload.notes)
        elif payload.status == "cancelled":
            r = await rebate_service.cancel_rebate(db, rebate_id, payload.notes)
        else:
            raise HTTPException(400, f"不支持的状态: {payload.status}")
        await db.commit()
        return r
    except RebateNotFoundError as e:
        raise HTTPException(404, str(e))
    except RebateError as e:
        raise HTTPException(400, str(e))


@router.post("/batch-pay")
@limiter.limit("30/minute")
async def batch_pay(request: Request, payload: RebateBatchPay, db: AsyncSession = Depends(get_db)):
    result = await rebate_service.batch_pay(db, payload.ids)
    await db.commit()
    return result
