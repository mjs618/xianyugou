"""回收站路由

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- 3 GET（customers/transactions/after-sales）→ 100/minute（读端点）
- 3 POST restore → 30/minute（写端点）
- 3 DELETE purge → 30/minute（写端点，不可逆操作）

404 语义：restore/purge 中「不存在」返回 404，「未被删除」等业务错误返回 400
（与 xianyu.py update_account/recover_account 的消息判断模式一致）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..security import limiter
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


def _trash_http_error(exc: ValueError) -> HTTPException:
    """「不存在」返回 404，其他业务错误返回 400（与 xianyu.py 模式一致）。"""
    msg = str(exc)
    status_code = 404 if msg.endswith("不存在") else 400
    return HTTPException(status_code, msg)


@router.get("/customers")
@limiter.limit("100/minute")
async def trashed_customers(request: Request, db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_customers(db)
    await db.commit()
    return [_customer_dict(c) for c in items]


@router.get("/transactions")
@limiter.limit("100/minute")
async def trashed_transactions(request: Request, db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_transactions(db)
    await db.commit()
    return [_transaction_dict(t) for t in items]


@router.get("/after-sales")
@limiter.limit("100/minute")
async def trashed_after_sales(request: Request, db: AsyncSession = Depends(get_db)):
    items = await trash_service.list_trashed_after_sales(db)
    await db.commit()
    return [_aftersales_dict(a) for a in items]


@router.post("/customers/{cid}/restore")
@limiter.limit("30/minute")
async def restore_customer(request: Request, cid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_customer(db, cid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)


@router.post("/transactions/{tid}/restore")
@limiter.limit("30/minute")
async def restore_transaction(request: Request, tid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_transaction(db, tid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)


@router.post("/after-sales/{aid}/restore")
@limiter.limit("30/minute")
async def restore_after_sales(request: Request, aid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.restore_after_sales(db, aid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)


@router.delete("/customers/{cid}/purge")
@limiter.limit("30/minute")
async def purge_customer(request: Request, cid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_customer(db, cid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)


@router.delete("/transactions/{tid}/purge")
@limiter.limit("30/minute")
async def purge_transaction(request: Request, tid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_transaction(db, tid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)


@router.delete("/after-sales/{aid}/purge")
@limiter.limit("30/minute")
async def purge_after_sales(request: Request, aid: int, db: AsyncSession = Depends(get_db)):
    try:
        await trash_service.purge_after_sales(db, aid)
        await db.commit()
        return {"ok": True}
    except ValueError as e:
        raise _trash_http_error(e)
