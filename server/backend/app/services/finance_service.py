"""财务统计聚合服务 - 复刻前端 financeService.ts（只读聚合）。"""
from datetime import datetime, timedelta
from typing import Optional
import calendar
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, RebateRecord, Customer, OperatingExpense
from ..utils.helpers import round2, now_utc
from .finance_calculations import (
    build_daily_trend,
    build_monthly_comparison,
    build_overview,
    build_product_profit_stats,
    month_range,
)


async def get_finance_overview(db: AsyncSession, *, month: bool = True) -> dict:
    """收支总览（本月 / 全部）。复刻 getFinanceOverview 的本月口径。"""
    now = now_utc()
    if month:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (start - timedelta(days=1)).replace(day=1)
        prev_end = start - timedelta(microseconds=1)
    else:
        start = datetime(1970, 1, 1)
        prev_start = datetime(1970, 1, 1)
        prev_end = datetime(1970, 1, 1)

    base = select(Transaction).where(Transaction.deleted_at.is_(None))
    cur_trades = list((await db.execute(base.where(Transaction.trade_at >= start))).scalars().all())
    prev_trades = list(
        (await db.execute(base.where(Transaction.trade_at >= prev_start, Transaction.trade_at <= prev_end))).scalars().all()
    ) if month else []

    if month:
        cur_expense = await _sum_expenses_between(db, start, now)
        prev_expense = await _sum_expenses_between(db, prev_start, prev_end)
    else:
        cur_expense = 0.0
        prev_expense = 0.0

    return build_overview(
        cur_trades,
        prev_trades,
        cur_expense=cur_expense,
        prev_expense=prev_expense,
    )


async def get_product_profit_stats(db: AsyncSession, start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[dict]:
    """商品利润排行。可选按 trade_at 范围过滤。"""
    stmt = select(Transaction).where(Transaction.deleted_at.is_(None))
    if start is not None:
        stmt = stmt.where(Transaction.trade_at >= start)
    if end is not None:
        stmt = stmt.where(Transaction.trade_at <= end)
    trades = list((await db.execute(stmt)).scalars().all())
    return build_product_profit_stats(trades)


async def get_customer_value_stats(db: AsyncSession, limit: int = 100) -> list[dict]:
    from ..models import Customer
    stmt = select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.total_spent.desc()).limit(limit)
    customers = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "customerId": c.id,
            "nickname": c.xianyu_nickname,
            "totalSpent": c.total_spent,
            "tradeCount": c.trade_count,
            "level": c.level,
        }
        for c in customers
    ]


async def _trades_between(db: AsyncSession, start: datetime, end: datetime) -> list[Transaction]:
    stmt = select(Transaction).where(
        Transaction.deleted_at.is_(None),
        Transaction.trade_at >= start,
        Transaction.trade_at <= end,
    )
    return list((await db.execute(stmt)).scalars().all())


async def _expenses_between(db: AsyncSession, start: datetime, end: datetime) -> list[OperatingExpense]:
    stmt = select(OperatingExpense).where(
        OperatingExpense.deleted_at.is_(None),
        OperatingExpense.occurred_at >= start,
        OperatingExpense.occurred_at <= end,
    )
    return list((await db.execute(stmt)).scalars().all())


async def _sum_expenses_between(db: AsyncSession, start: datetime, end: datetime) -> float:
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


async def get_finance_overview_by_range(db: AsyncSession, start: datetime, end: datetime) -> dict:
    """自定义时间范围收支总览，环比 = 上一同等长度周期。"""
    cur = await _trades_between(db, start, end)
    duration = end - start
    prev_end = start - timedelta(microseconds=1)
    prev_start = prev_end - duration
    prev = await _trades_between(db, prev_start, prev_end)
    cur_expense = await _sum_expenses_between(db, start, end)
    prev_expense = await _sum_expenses_between(db, prev_start, prev_end)
    return build_overview(
        cur,
        prev,
        cur_expense=cur_expense,
        prev_expense=prev_expense,
    )


async def get_trend(db: AsyncSession, days: int = 30) -> list[dict]:
    """近 N 天每日收支趋势（复刻前端 getTrend）。"""
    end = now_utc()
    start = (end - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    trades = await _trades_between(db, start, end)
    expenses = await _expenses_between(db, start, end)
    return build_daily_trend(trades, expenses, start, end)


async def get_monthly_comparison(db: AsyncSession, months: int = 6) -> list[dict]:
    """近 N 月对比（复刻前端 getMonthlyComparison）。"""
    now = now_utc()
    start = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=(months - 1) * 31))  # 近似往前推 months 个月
    # 精确算到 months 个月前的月初
    y, m = now.year, now.month
    for _ in range(months - 1):
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    start = datetime(y, m, 1)
    trades = await _trades_between(db, start, now)
    expenses = await _expenses_between(db, start, now)
    return build_monthly_comparison(
        trades,
        expenses,
        start_year=y,
        start_month=m,
        months=months,
    )


async def get_new_customer_count(db: AsyncSession, date: Optional[datetime] = None) -> int:
    """本月新客户数（first_trade_at 在本月）。"""
    d = date or now_utc()
    start, end = month_range(d)
    cnt = (
        await db.execute(
            select(func.count(Customer.id)).where(
                Customer.deleted_at.is_(None),
                Customer.first_trade_at.is_not(None),
                Customer.first_trade_at >= start,
                Customer.first_trade_at <= end,
            )
        )
    ).scalar_one()
    return cnt


async def get_new_customer_count_by_range(db: AsyncSession, start: datetime, end: datetime) -> int:
    """指定时间范围新客户数。"""
    cnt = (
        await db.execute(
            select(func.count(Customer.id)).where(
                Customer.deleted_at.is_(None),
                Customer.first_trade_at.is_not(None),
                Customer.first_trade_at >= start,
                Customer.first_trade_at <= end,
            )
        )
    ).scalar_one()
    return cnt
