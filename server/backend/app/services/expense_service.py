"""运营支出服务。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import OperatingExpense
from ..utils.helpers import now_utc, round2


async def list_expenses(
    db: AsyncSession,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> list[OperatingExpense]:
    stmt = select(OperatingExpense).where(OperatingExpense.deleted_at.is_(None))
    if start is not None:
        stmt = stmt.where(OperatingExpense.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(OperatingExpense.occurred_at <= end)
    stmt = stmt.order_by(OperatingExpense.occurred_at.desc(), OperatingExpense.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def create_expense(
    db: AsyncSession,
    *,
    category: str,
    amount: float,
    occurred_at: datetime,
    notes: Optional[str] = None,
) -> OperatingExpense:
    expense = OperatingExpense(
        category=category.strip() or "擦亮",
        amount=round2(amount),
        occurred_at=occurred_at,
        notes=notes,
    )
    db.add(expense)
    await db.flush()
    return expense


async def update_expense(db: AsyncSession, expense_id: int, patch: dict) -> OperatingExpense:
    expense = await db.get(OperatingExpense, expense_id)
    if not expense or expense.deleted_at is not None:
        raise ValueError("支出记录不存在")
    if "category" in patch and patch["category"] is not None:
        expense.category = patch["category"].strip() or "擦亮"
    if "amount" in patch and patch["amount"] is not None:
        expense.amount = round2(patch["amount"])
    if "occurred_at" in patch and patch["occurred_at"] is not None:
        expense.occurred_at = patch["occurred_at"]
    if "notes" in patch:
        expense.notes = patch["notes"]
    await db.flush()
    return expense


async def delete_expense(db: AsyncSession, expense_id: int) -> None:
    expense = await db.get(OperatingExpense, expense_id)
    if not expense or expense.deleted_at is not None:
        raise ValueError("支出记录不存在")
    expense.deleted_at = now_utc()
    await db.flush()


async def sum_expenses_between(db: AsyncSession, start: datetime, end: datetime) -> float:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(OperatingExpense.amount), 0.0)).where(
                OperatingExpense.deleted_at.is_(None),
                OperatingExpense.occurred_at >= start,
                OperatingExpense.occurred_at <= end,
            )
        )
    ).scalar_one()
    return round2(float(total or 0.0))
