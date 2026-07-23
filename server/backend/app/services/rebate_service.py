"""返利服务 - 复刻前端 rebateService.ts（状态机 + 重算）。"""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RebateRecord, Transaction
from ..utils.helpers import round2, now_utc
from .audit_service import log_operation
from .settings_service import get_settings


class RebateError(ValueError):
    pass


class RebateNotFoundError(RebateError):
    """返利记录不存在（路由层捕获后返回 404，对齐 aftersales/warranty/customers）。"""
    pass


# 合法流转：pending → paid/cancelled；paid → cancelled；其余非法
VALID_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["cancelled"],
    "cancelled": [],
}


def _validate_transition(frm: str, to: str) -> None:
    if frm == to:
        return
    allowed = VALID_TRANSITIONS.get(frm, [])
    if to not in allowed:
        raise RebateError(f"非法的返利状态流转：{frm} → {to}（仅允许 pending→paid/cancelled、paid→cancelled）")


async def list_rebates(db: AsyncSession) -> list[RebateRecord]:
    stmt = select(RebateRecord).order_by(RebateRecord.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def get_rebate(db: AsyncSession, rebate_id: int) -> RebateRecord | None:
    return await db.get(RebateRecord, rebate_id)


async def get_rebate_by_transaction(db: AsyncSession, tx_id: int) -> RebateRecord | None:
    return (
        await db.execute(select(RebateRecord).where(RebateRecord.transaction_id == tx_id).limit(1))
    ).scalar_one_or_none()


async def list_by_referrer(db: AsyncSession, referrer_id: int) -> list[RebateRecord]:
    stmt = select(RebateRecord).where(RebateRecord.referrer_id == referrer_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_pending_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(RebateRecord.id)).where(RebateRecord.status == "pending")
        )
    ).scalar_one()


async def get_pending_total(db: AsyncSession) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(RebateRecord.amount), 0)).where(RebateRecord.status == "pending")
        )
    ).scalar_one()
    return round(float(total) + 1e-9, 2)


async def get_total_paid(db: AsyncSession) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(RebateRecord.amount), 0)).where(RebateRecord.status == "paid")
        )
    ).scalar_one()
    return round(float(total) + 1e-9, 2)


async def mark_paid(db: AsyncSession, rebate_id: int, notes: str | None = None) -> RebateRecord:
    r = await get_rebate(db, rebate_id)
    if r is None:
        raise RebateNotFoundError("返利记录不存在")
    _validate_transition(r.status, "paid")
    r.status = "paid"
    r.paid_at = now_utc()
    if notes is not None:
        r.notes = notes
    await db.flush()
    await log_operation(db, "rebate", "status_change", target_id=rebate_id, detail=f"标记已支付（金额:¥{r.amount}）")
    return r


async def cancel_rebate(db: AsyncSession, rebate_id: int, notes: str | None = None) -> RebateRecord:
    r = await get_rebate(db, rebate_id)
    if r is None:
        raise RebateNotFoundError("返利记录不存在")
    _validate_transition(r.status, "cancelled")
    r.status = "cancelled"
    if notes is not None:
        r.notes = notes
    await db.flush()
    await log_operation(db, "rebate", "status_change", target_id=rebate_id, detail=f"取消返利（金额:¥{r.amount}）")
    return r


async def batch_pay(db: AsyncSession, ids: list[int]) -> dict:
    """批量结算。只结算 pending，跳过非法状态。"""
    now = now_utc()
    # 批量加载所有 rebate，避免循环内 N+1 查询
    unique_ids = list(dict.fromkeys(ids))  # 去重保序
    rebates_map: dict[int, RebateRecord] = {}
    if unique_ids:
        rows = (await db.execute(
            select(RebateRecord).where(RebateRecord.id.in_(unique_ids))
        )).scalars().all()
        rebates_map = {r.id: r for r in rows if r.id is not None}
    valid: list[RebateRecord] = []
    skipped = 0
    for rid in unique_ids:
        r = rebates_map.get(rid)
        if r is None:
            skipped += 1
            continue
        # 批量结算语义：只处理 pending 状态。paid/cancelled 一律跳过
        # （不能用 _validate_transition，因为 paid→paid 是 idempotent no-op 会被误判为合法）。
        if r.status != "pending":
            skipped += 1
            continue
        valid.append(r)
    for r in valid:
        r.status = "paid"
        r.paid_at = now
    await db.flush()
    extra = f"（跳过 {skipped} 笔非法状态）" if skipped > 0 else ""
    await log_operation(db, "rebate", "batch_pay", detail=f"批量结算 {len(valid)} 笔返利{extra}")
    return {"updated": len(valid), "skipped": skipped}


async def recalc_pending_rebates(db: AsyncSession) -> int:
    """按最新设置重算所有待结算返利金额（设置变更后调用）。"""
    s = await get_settings(db)
    pending = list(
        (await db.execute(select(RebateRecord).where(RebateRecord.status == "pending"))).scalars().all()
    )
    # 批量预取交易，避免循环内逐个 db.get 导致 N+1 查询
    tx_ids = [r.transaction_id for r in pending if r.transaction_id is not None]
    tx_map: dict[int, Transaction] = {}
    if tx_ids:
        rows = (await db.execute(
            select(Transaction).where(Transaction.id.in_(tx_ids))
        )).scalars().all()
        tx_map = {t.id: t for t in rows if t.id is not None}
    updated = 0
    for r in pending:
        t = tx_map.get(r.transaction_id)
        if t is None:
            continue
        base = t.sale_price if s.rebate_base == "sale" else t.profit
        new_amount = round2(base * s.rebate_rate)
        if new_amount != r.amount or s.rebate_rate != r.rate:
            r.amount = new_amount
            r.rate = s.rebate_rate
            updated += 1
    await db.flush()
    return updated
