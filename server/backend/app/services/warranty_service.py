"""质保监控服务 - 复刻前端 warrantyService.ts 的查询逻辑。"""
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, WarrantyExtension
from ..utils.helpers import now_utc


async def get_active_transactions(db: AsyncSession) -> list[Transaction]:
    """质保进行中（未过期）"""
    now = now_utc()
    urgent = now + timedelta(days=3)
    stmt = (
        select(Transaction)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.warranty_end.is_not(None),
            Transaction.warranty_end > urgent),
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_urgent_transactions(db: AsyncSession) -> list[Transaction]:
    """即将到期（3天内）"""
    now = now_utc()
    urgent = now + timedelta(days=3)
    stmt = (
        select(Transaction)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.warranty_end.is_not(None),
            Transaction.warranty_end > now,
            Transaction.warranty_end <= urgent,
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def count_urgent_transactions(db: AsyncSession) -> int:
    """即将到期（3天内）交易计数 - 用 COUNT 替代加载完整对象。"""
    now = now_utc()
    urgent = now + timedelta(days=3)
    return (await db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.deleted_at.is_(None),
            Transaction.warranty_end.is_not(None),
            Transaction.warranty_end > now,
            Transaction.warranty_end <= urgent,
        )
    )).scalar_one()


async def get_expired_transactions(db: AsyncSession) -> list[Transaction]:
    """已过期"""
    now = now_utc()
    stmt = (
        select(Transaction)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.warranty_end.is_not(None),
            Transaction.warranty_end <= now,
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_all_warranty_transactions(db: AsyncSession) -> list[Transaction]:
    """所有有质保的交易"""
    stmt = select(Transaction).where(
        Transaction.deleted_at.is_(None), Transaction.warranty_end.is_not(None)
    ).order_by(Transaction.warranty_end.asc())
    return list((await db.execute(stmt)).scalars().all())


async def extend_warranty(
    db: AsyncSession, tx_id: int, days: int, reason: str | None = None
) -> Transaction:
    """延长质保。记录历史。"""
    t = await db.get(Transaction, tx_id)
    if t is None or t.deleted_at is not None:
        raise ValueError("交易不存在")
    if days <= 0:
        raise ValueError("延长天数必须大于 0")
    old_end = t.warranty_end or now_utc()
    new_end = old_end + timedelta(days=days)
    db.add(WarrantyExtension(
        transaction_id=tx_id, old_end=old_end, new_end=new_end,
        extended_days=days, reason=reason,
    ))
    t.warranty_end = new_end
    t.warranty_days = (t.warranty_days or 0) + days  # 累加质保天数（与前端逻辑一致）
    t.updated_at = now_utc()
    await db.flush()
    return t


async def end_warranty_early(db: AsyncSession, tx_id: int) -> Transaction:
    """提前结束质保。"""
    t = await db.get(Transaction, tx_id)
    if t is None or t.deleted_at is not None:
        raise ValueError("交易不存在")
    old_end = t.warranty_end or now_utc()
    new_end = now_utc()
    db.add(WarrantyExtension(
        transaction_id=tx_id, old_end=old_end, new_end=new_end,
        extended_days=0, reason="提前结束质保",
    ))
    t.warranty_end = new_end
    t.updated_at = now_utc()
    await db.flush()
    return t


async def get_warranty_extensions(db: AsyncSession, tx_id: int) -> list[WarrantyExtension]:
    """获取某交易的质保延长历史。"""
    stmt = select(WarrantyExtension).where(
        WarrantyExtension.transaction_id == tx_id
    ).order_by(WarrantyExtension.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())
