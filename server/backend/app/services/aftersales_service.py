"""售后工单服务 - 复刻前端 afterSalesService.ts（状态机 + 交易状态联动）。"""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AfterSales, Transaction
from ..utils.helpers import now_utc
from .audit_service import log_operation
from .transaction_service import change_status


class AfterSalesError(ValueError):
    pass


async def get_aftersales(db: AsyncSession, ticket_id: int) -> AfterSales | None:
    a = await db.get(AfterSales, ticket_id)
    if a is None or a.deleted_at is not None:
        return None
    return a


async def list_aftersales(db: AsyncSession) -> list[AfterSales]:
    stmt = select(AfterSales).where(AfterSales.deleted_at.is_(None)).order_by(AfterSales.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def list_by_transaction(db: AsyncSession, tx_id: int) -> list[AfterSales]:
    stmt = select(AfterSales).where(
        AfterSales.transaction_id == tx_id, AfterSales.deleted_at.is_(None)
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_aftersales(
    db: AsyncSession,
    *,
    transaction_id: int,
    issue_desc: str,
    attachments: list[str] | None = None,
) -> AfterSales:
    tx = await db.get(Transaction, transaction_id)
    if tx is None or tx.deleted_at is not None:
        raise AfterSalesError("交易不存在")

    original_status = tx.status if tx.status != "aftersales" else None
    a = AfterSales(
        transaction_id=transaction_id,
        issue_desc=issue_desc,
        status="pending",
        attachments=attachments or [],
        original_transaction_status=original_status,
        created_at=now_utc(),
    )
    db.add(a)
    await db.flush()

    if tx.status != "aftersales":
        await change_status(db, transaction_id, "aftersales")

    await log_operation(
        db, "aftersales", "create", target_id=a.id,
        detail=f"交易ID:{transaction_id} 问题:{issue_desc[:50]}",
    )
    return a


async def delete_aftersales(db: AsyncSession, ticket_id: int) -> None:
    a = await get_aftersales(db, ticket_id)
    if a is None:
        raise AfterSalesError("工单不存在")
    a.deleted_at = now_utc()
    await db.flush()
    await log_operation(db, "aftersales", "delete", target_id=ticket_id, detail=f"工单:{a.issue_desc[:30]}")


async def update_status(
    db: AsyncSession,
    ticket_id: int,
    status: str,
    solution_type: str | None = None,
    solution_desc: str | None = None,
) -> AfterSales:
    """更新工单状态。resolved/closed 时计算耗时并尝试恢复交易状态。"""
    a = await get_aftersales(db, ticket_id)
    if a is None:
        raise AfterSalesError("工单不存在")

    a.status = status
    if solution_type:
        a.solution_type = solution_type
    if solution_desc is not None:
        a.solution_desc = solution_desc
    if status in ("resolved", "closed"):
        a.resolved_at = now_utc()
        if a.created_at:
            delta = a.resolved_at - a.created_at
            a.duration_hours = round(delta.total_seconds() / 3600)
    await db.flush()

    # resolved/closed 且无其他 open 工单时，恢复交易状态
    if status in ("resolved", "closed"):
        open_count = (
            await db.execute(
                select(func.count(AfterSales.id)).where(
                    AfterSales.transaction_id == a.transaction_id,
                    AfterSales.deleted_at.is_(None),
                    AfterSales.status.in_(["pending", "processing"]),
                )
            )
        ).scalar_one()
        if open_count == 0:
            tickets = list(
                (await db.execute(
                    select(AfterSales).where(AfterSales.transaction_id == a.transaction_id)
                    .order_by(AfterSales.created_at.asc())
                )).scalars().all()
            )
            earliest = next((t for t in tickets if t.original_transaction_status), None)
            restore = earliest.original_transaction_status if earliest and earliest.original_transaction_status else "completed"
            await change_status(db, a.transaction_id, restore)

    await log_operation(
        db, "aftersales", "status_change", target_id=ticket_id,
        detail=f"状态变更为 {status}" + (f"（解决方式: {solution_type}）" if solution_type else ""),
    )
    return a


async def get_pending_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(AfterSales.id)).where(
                AfterSales.deleted_at.is_(None),
                AfterSales.status.in_(["pending", "processing"]),
            )
        )
    ).scalar_one()


async def get_after_sales_stats(db: AsyncSession) -> dict:
    """售后统计：总数/待处理/已解决/平均耗时/售后率。复刻前端 getAfterSalesStats。"""
    all_tickets = list(
        (await db.execute(select(AfterSales).where(AfterSales.deleted_at.is_(None)))).scalars().all()
    )
    total_trades = (
        await db.execute(select(func.count(Transaction.id)).where(Transaction.deleted_at.is_(None)))
    ).scalar_one()
    resolved = [a for a in all_tickets if a.status in ("resolved", "closed")]
    avg_duration = (
        round(sum((a.duration_hours or 0) for a in resolved) / len(resolved))
        if resolved else 0
    )
    return {
        "totalCount": len(all_tickets),
        "pendingCount": len([a for a in all_tickets if a.status in ("pending", "processing")]),
        "resolvedCount": len(resolved),
        "avgDurationHours": avg_duration,
        "rate": len(all_tickets) / total_trades if total_trades > 0 else 0,
    }


async def get_top_issue_products(db: AsyncSession, limit: int = 10) -> list[dict]:
    """高频问题商品（内存 join 工单→交易）。复刻前端 getTopIssueProducts。"""
    all_tickets = list((await db.execute(select(AfterSales))).scalars().all())
    all_trades = list((await db.execute(select(Transaction))).scalars().all())
    tx_by_id = {t.id: t for t in all_trades if t.id is not None}
    agg: dict[str, int] = {}
    for a in all_tickets:
        t = tx_by_id.get(a.transaction_id)
        if t is None:
            continue
        agg[t.product_name] = agg.get(t.product_name, 0) + 1
    result = [{"productName": k, "count": v} for k, v in agg.items()]
    result.sort(key=lambda x: x["count"], reverse=True)
    return result[:limit]

