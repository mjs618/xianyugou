"""质保监控路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import TransactionOut
from ..services import warranty_service

router = APIRouter(prefix="/api/warranty", tags=["warranty"])


@router.get("/active", response_model=list[TransactionOut])
async def active(db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_active_transactions(db)
    await db.commit()
    return items


@router.get("/urgent", response_model=list[TransactionOut])
async def urgent(db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_urgent_transactions(db)
    await db.commit()
    return items


@router.get("/expired", response_model=list[TransactionOut])
async def expired(db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_expired_transactions(db)
    await db.commit()
    return items


@router.get("/all", response_model=list[TransactionOut])
async def all_warranty(db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_all_warranty_transactions(db)
    await db.commit()
    return items


@router.post("/{tx_id}/extend", response_model=TransactionOut)
async def extend(tx_id: int, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    days = payload.get("days")
    reason = payload.get("reason")
    if not days or days <= 0:
        raise HTTPException(400, "延长天数必须大于 0")
    try:
        t = await warranty_service.extend_warranty(db, tx_id, days, reason)
        await db.commit()
        return t
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{tx_id}/end-early", response_model=TransactionOut)
async def end_early(tx_id: int, payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    reason = payload.get("reason")
    try:
        t = await warranty_service.end_warranty_early(db, tx_id)
        await db.commit()
        return t
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{tx_id}/extensions")
async def extensions(tx_id: int, db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_warranty_extensions(db, tx_id)
    await db.commit()
    # 序列化日期
    return [
        {
            "id": e.id, "transaction_id": e.transaction_id,
            "old_end": e.old_end.isoformat() if e.old_end else None,
            "new_end": e.new_end.isoformat() if e.new_end else None,
            "extended_days": e.extended_days, "reason": e.reason,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in items
    ]
