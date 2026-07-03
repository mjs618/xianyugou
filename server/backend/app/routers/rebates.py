"""返利路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import RebateStatusChange, RebateBatchPay, RebateOut
from ..services import rebate_service
from ..services.rebate_service import RebateError

router = APIRouter(prefix="/api/rebates", tags=["rebates"])


@router.get("", response_model=list[RebateOut])
async def list_rebates(db: AsyncSession = Depends(get_db)):
    items = await rebate_service.list_rebates(db)
    await db.commit()
    return items


@router.get("/pending-count")
async def pending_count(db: AsyncSession = Depends(get_db)):
    count = await rebate_service.get_pending_count(db)
    await db.commit()
    return {"count": count}


@router.get("/pending-total")
async def pending_total(db: AsyncSession = Depends(get_db)):
    total = await rebate_service.get_pending_total(db)
    await db.commit()
    return {"total": total}


@router.get("/by-referrer/{referrer_id}", response_model=list[RebateOut])
async def by_referrer(referrer_id: int, db: AsyncSession = Depends(get_db)):
    items = await rebate_service.list_by_referrer(db, referrer_id)
    await db.commit()
    return items


@router.get("/by-transaction/{tx_id}")
async def by_transaction(tx_id: int, db: AsyncSession = Depends(get_db)):
    r = await rebate_service.get_rebate_by_transaction(db, tx_id)
    await db.commit()
    return r


@router.patch("/{rebate_id}")
async def update_rebate_status(rebate_id: int, payload: RebateStatusChange, db: AsyncSession = Depends(get_db)):
    try:
        if payload.status == "paid":
            r = await rebate_service.mark_paid(db, rebate_id, payload.notes)
        elif payload.status == "cancelled":
            r = await rebate_service.cancel_rebate(db, rebate_id, payload.notes)
        else:
            raise HTTPException(400, f"不支持的状态: {payload.status}")
        await db.commit()
        return r
    except RebateError as e:
        raise HTTPException(400, str(e))


@router.post("/batch-pay")
async def batch_pay(payload: RebateBatchPay, db: AsyncSession = Depends(get_db)):
    result = await rebate_service.batch_pay(db, payload.ids)
    await db.commit()
    return result
