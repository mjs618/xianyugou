"""质保监控路由。

读端点 100 req/min/IP，写端点 30 req/min/IP（project_memory 硬约束：
stricter for write endpoints）。

错误语义对齐 expenses/mail_record/aftersales：交易不存在返回 404，
业务校验失败（如延长天数 ≤ 0）返回 400。
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import TransactionOut, WarrantyEndEarly, WarrantyExtend
from ..security import limiter
from ..services import warranty_service
from ..services.warranty_service import WarrantyError, WarrantyNotFoundError

router = APIRouter(prefix="/api/warranty", tags=["warranty"])


@router.get("/active", response_model=list[TransactionOut])
@limiter.limit("100/minute")
async def active(request: Request, db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_active_transactions(db)
    await db.commit()
    return items


@router.get("/urgent", response_model=list[TransactionOut])
@limiter.limit("100/minute")
async def urgent(request: Request, db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_urgent_transactions(db)
    await db.commit()
    return items


@router.get("/expired", response_model=list[TransactionOut])
@limiter.limit("100/minute")
async def expired(request: Request, db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_expired_transactions(db)
    await db.commit()
    return items


@router.get("/all", response_model=list[TransactionOut])
@limiter.limit("100/minute")
async def all_warranty(request: Request, db: AsyncSession = Depends(get_db)):
    items = await warranty_service.get_all_warranty_transactions(db)
    await db.commit()
    return items


@router.post("/{tx_id}/extend", response_model=TransactionOut)
@limiter.limit("30/minute")
async def extend(
    request: Request,
    tx_id: int,
    payload: WarrantyExtend = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await warranty_service.extend_warranty(db, tx_id, payload.days, payload.reason)
        await db.commit()
        return t
    except WarrantyNotFoundError as e:
        raise HTTPException(404, str(e))
    except WarrantyError as e:
        raise HTTPException(400, str(e))


@router.post("/{tx_id}/end-early", response_model=TransactionOut)
@limiter.limit("30/minute")
async def end_early(
    request: Request,
    tx_id: int,
    payload: WarrantyEndEarly = Body(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await warranty_service.end_warranty_early(db, tx_id)
        await db.commit()
        return t
    except WarrantyNotFoundError as e:
        raise HTTPException(404, str(e))
    except WarrantyError as e:
        raise HTTPException(400, str(e))


@router.get("/{tx_id}/extensions")
@limiter.limit("100/minute")
async def extensions(request: Request, tx_id: int, db: AsyncSession = Depends(get_db)):
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
