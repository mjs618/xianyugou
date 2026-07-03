"""回收站服务 - 复刻前端 trashService.ts。

含：列出软删除记录、恢复（带校验+级联 recalc）、彻底删除（级联清理关联数据）、过期清理。
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Customer, Transaction, AfterSales, RebateRecord, CustomerLink,
    CustomerTagRelation, WarrantyExtension,
)
from ..utils.helpers import now_utc
from .customer_service import recalc_customer_stats


SOFT_DELETE_RETENTION_DAYS = 30
AUDIT_LOG_RETENTION_DAYS = 90
NOTIFICATION_RETENTION_DAYS = 30


# ==================== 列出软删除记录 ====================

async def list_trashed_customers(db: AsyncSession) -> list[Customer]:
    stmt = select(Customer).where(Customer.deleted_at.is_not(None)).order_by(Customer.updated_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_trashed_transactions(db: AsyncSession) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.deleted_at.is_not(None)).order_by(Transaction.updated_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_trashed_after_sales(db: AsyncSession) -> list[AfterSales]:
    stmt = select(AfterSales).where(AfterSales.deleted_at.is_not(None)).order_by(AfterSales.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


# ==================== 恢复 ====================

async def restore_customer(db: AsyncSession, customer_id: int) -> None:
    c = await db.get(Customer, customer_id)
    if c is None:
        raise ValueError("客户不存在")
    if not c.deleted_at:
        raise ValueError("该客户未被删除")
    # 恢复前校验昵称唯一性
    lower = c.xianyu_nickname.lower()
    conflicting = (
        await db.execute(
            select(Customer).where(
                Customer.deleted_at.is_(None),
                Customer.id != customer_id,
                func.lower(Customer.xianyu_nickname) == lower,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if conflicting:
        raise ValueError(f'昵称"{c.xianyu_nickname}"已被其他客户占用，请先修改后再恢复')
    c.deleted_at = None
    c.updated_at = now_utc()
    await db.flush()
    await recalc_customer_stats(db, customer_id)


async def restore_transaction(db: AsyncSession, tx_id: int) -> None:
    t = await db.get(Transaction, tx_id)
    if t is None:
        raise ValueError("交易不存在")
    if not t.deleted_at:
        raise ValueError("该交易未被删除")
    customer = await db.get(Customer, t.customer_id)
    if customer is None or customer.deleted_at:
        raise ValueError("关联客户已被删除，请先恢复客户")
    t.deleted_at = None
    t.updated_at = now_utc()
    await db.flush()
    await recalc_customer_stats(db, t.customer_id)


async def restore_after_sales(db: AsyncSession, ticket_id: int) -> None:
    a = await db.get(AfterSales, ticket_id)
    if a is None:
        raise ValueError("工单不存在")
    if not a.deleted_at:
        raise ValueError("该工单未被删除")
    tx = await db.get(Transaction, a.transaction_id)
    if tx is None or tx.deleted_at:
        raise ValueError("关联交易已被删除，请先恢复交易")
    a.deleted_at = None
    await db.flush()


# ==================== 彻底删除 ====================

async def purge_customer(db: AsyncSession, customer_id: int) -> None:
    c = await db.get(Customer, customer_id)
    if c is None:
        raise ValueError("客户不存在")
    if not c.deleted_at:
        raise ValueError("仅可彻底删除回收站中的客户")
    # 删除关联交易及其子数据
    trades = list((await db.execute(
        select(Transaction).where(Transaction.customer_id == customer_id)
    )).scalars().all())
    trade_ids = [t.id for t in trades if t.id]
    if trade_ids:
        await db.execute(delete(AfterSales).where(AfterSales.transaction_id.in_(trade_ids)))
        await db.execute(delete(RebateRecord).where(RebateRecord.transaction_id.in_(trade_ids)))
        await db.execute(delete(WarrantyExtension).where(WarrantyExtension.transaction_id.in_(trade_ids)))
    await db.execute(delete(Transaction).where(Transaction.customer_id == customer_id))
    # 推荐关系
    await db.execute(delete(CustomerLink).where(
        (CustomerLink.referrer_id == customer_id) | (CustomerLink.buyer_id == customer_id)
    ))
    # 标签关系
    await db.execute(delete(CustomerTagRelation).where(CustomerTagRelation.customer_id == customer_id))
    await db.delete(c)
    await db.flush()


async def purge_transaction(db: AsyncSession, tx_id: int) -> None:
    t = await db.get(Transaction, tx_id)
    if t is None:
        raise ValueError("交易不存在")
    if not t.deleted_at:
        raise ValueError("仅可彻底删除回收站中的交易")
    await db.execute(delete(AfterSales).where(AfterSales.transaction_id == tx_id))
    await db.execute(delete(RebateRecord).where(RebateRecord.transaction_id == tx_id))
    await db.execute(delete(WarrantyExtension).where(WarrantyExtension.transaction_id == tx_id))
    await db.delete(t)
    await db.flush()


async def purge_after_sales(db: AsyncSession, ticket_id: int) -> None:
    a = await db.get(AfterSales, ticket_id)
    if a is None:
        raise ValueError("工单不存在")
    if not a.deleted_at:
        raise ValueError("仅可彻底删除回收站中的工单")
    await db.delete(a)
    await db.flush()


# ==================== 过期清理 ====================

async def cleanup_expired_soft_deletes(db: AsyncSession) -> dict:
    cutoff = now_utc() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    result = {"customers": 0, "transactions": 0, "afterSales": 0}
    # 过期客户
    expired_customers = list((await db.execute(
        select(Customer).where(Customer.deleted_at.is_not(None), Customer.deleted_at < cutoff)
    )).scalars().all())
    for c in expired_customers:
        if c.id:
            try:
                await purge_customer(db, c.id)
                result["customers"] += 1
            except Exception as e:
                print(f"清理过期客户失败: {e}")
    # 过期交易
    expired_trades = list((await db.execute(
        select(Transaction).where(Transaction.deleted_at.is_not(None), Transaction.deleted_at < cutoff)
    )).scalars().all())
    for t in expired_trades:
        if t.id:
            try:
                await purge_transaction(db, t.id)
                result["transactions"] += 1
            except Exception as e:
                print(f"清理过期交易失败: {e}")
    # 过期工单
    expired_tickets = list((await db.execute(
        select(AfterSales).where(AfterSales.deleted_at.is_not(None), AfterSales.deleted_at < cutoff)
    )).scalars().all())
    for a in expired_tickets:
        if a.id:
            try:
                await purge_after_sales(db, a.id)
                result["afterSales"] += 1
            except Exception as e:
                print(f"清理过期工单失败: {e}")
    return result


async def run_all_cleanup(db: AsyncSession) -> None:
    """执行所有清理任务。"""
    try:
        await cleanup_expired_soft_deletes(db)
        # 审计日志/通知清理也由后端负责（此处可选实现）
    except Exception as e:
        print(f"清理任务执行失败: {e}")
