"""回收站路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import trash_service

router = APIRouter(prefix="/api/trash", tags=["trash"])


def _customer_dict(c) -> dict:
    return {
        "id": c.id, "xianyu_nickname": c.xianyu_nickname, "level": c.level,
        "is_blacklist": c.is_blacklist, "total_spent": c.total_spent,
        "deleted_at": c.deleted_at.isoformat() if c.deleted_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _transaction_dict(t) -> dict:
    return {
        "id": t.id, "customer_id": t.customer_id, "product_name": t.product_name,
        "sale_price": t.sale_price, "status": t.status,
        "deleted_at": t.deleted_at.isoformat() if t.deleted_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _aftersales_dict(a) -> dict:
    return {
        "id": a.id, "transaction_id": a.transaction_id, "issue_desc": a.issue_desc,
        "status": a.status, "deleted_at": a.deleted_at.isoformat() if a.deleted_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/customers")
async def trashed_customers(db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_customers(db)
    await db.commit()
    return [_customer_dict(c) for c in items]


@router.get("/transactions")
async def trashed_transactions(db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_transactions(db)
    await db.commit()
    return [_transaction_dict(t) for t in items]


@router.get("/after-sales")
async def trashed_after_sales(db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_after_sales(db)
    await db.commit()
    return [_aftersales_dict(a) for a in items]


@router.post("/customers/{cid}/restore")
async def restore_customer(cid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_customer(db, cid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/transactions/{tid}/restore")
async def restore_transaction(tid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_transaction(db, tid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/after-sales/{aid}/restore")
async def restore_after_sales(aid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_after_sales(db, aid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/customers/{cid}/purge")
async def purge_customer(cid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_customer(db, cid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/transactions/{tid}/purge")
async def purge_transaction(tid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_transaction(db, tid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/after-sales/{aid}/purge")
async def purge_after_sales(aid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_after_sales(db, aid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))
