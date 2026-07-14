"""财务统计聚合服务 - 复刻前端 financeService.ts（只读聚合）。

所有交易查询使用 SQL 聚合（SUM/COUNT/GROUP BY）替代加载 ORM 对象到内存，
并排除 status='closed'（全额退款）交易以符合「净收入归零」设计规范。
"""
from datetime import datetime, timedelta
from typing import Optional
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


# ==================== SQL 聚合辅助函数 ====================

async def _trade_agg_between(
    db: AsyncSession, start: datetime, end: datetime, channel: Optional[str] = None
) -> dict:
    """单条 SQL 聚合：返回 {income, cost, profit, count}（排除 closed/deleted）。
    channel 非空时仅统计指定销售渠道。"""
    stmt = (
        select(
            func.coalesce(func.sum(Transaction.sale_price), 0.0).label("income"),
            func.coalesce(func.sum(Transaction.cost_price), 0.0).label("cost"),
            func.coalesce(func.sum(Transaction.profit), 0.0).label("profit"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.status != "closed",
            Transaction.trade_at >= start,
            Transaction.trade_at <= end,
        )
    )
    if channel is not None:
        stmt = stmt.where(Transaction.channel == channel)
    row = (await db.execute(stmt)).one()
    return {
        "income": float(row.income or 0),
        "cost": float(row.cost or 0),
        "profit": float(row.profit or 0),
        "count": row.count,
    }


async def _product_agg_between(
    db: AsyncSession,
    start: Optional[datetime],
    end: Optional[datetime],
    channel: Optional[str] = None,
) -> list:
    """SQL GROUP BY product_name，返回命名行列表（product_name/income/cost/profit/count）。
    channel 非空时仅统计指定销售渠道。"""
    stmt = (
        select(
            Transaction.product_name.label("product_name"),
            func.coalesce(func.sum(Transaction.sale_price), 0.0).label("income"),
            func.coalesce(func.sum(Transaction.cost_price), 0.0).label("cost"),
            func.coalesce(func.sum(Transaction.profit), 0.0).label("profit"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.status != "closed",
        )
        .group_by(Transaction.product_name)
    )
    if start is not None:
        stmt = stmt.where(Transaction.trade_at >= start)
    if end is not None:
        stmt = stmt.where(Transaction.trade_at <= end)
    if channel is not None:
        stmt = stmt.where(Transaction.channel == channel)
    return list((await db.execute(stmt)).all())


async def _trade_daily_agg(
    db: AsyncSession, start: datetime, end: datetime, channel: Optional[str] = None
) -> dict[str, dict]:
    """SQL GROUP BY date(trade_at)，返回 {"YYYY-MM-DD": {income,cost,profit,count}}。
    channel 非空时仅统计指定销售渠道。"""
    stmt = (
        select(
            func.date(Transaction.trade_at).label("day"),
            func.coalesce(func.sum(Transaction.sale_price), 0.0).label("income"),
            func.coalesce(func.sum(Transaction.cost_price), 0.0).label("cost"),
            func.coalesce(func.sum(Transaction.profit), 0.0).label("profit"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.status != "closed",
            Transaction.trade_at >= start,
            Transaction.trade_at <= end,
        )
        .group_by(func.date(Transaction.trade_at))
    )
    if channel is not None:
        stmt = stmt.where(Transaction.channel == channel)
    rows = (await db.execute(stmt)).all()
    return {
        r.day: {
            "income": float(r.income or 0),
            "cost": float(r.cost or 0),
            "profit": float(r.profit or 0),
            "count": r.count,
        }
        for r in rows
    }


async def _expense_daily_agg(
    db: AsyncSession, start: datetime, end: datetime
) -> dict[str, float]:
    """SQL GROUP BY date(occurred_at)，返回 {"YYYY-MM-DD": total_amount}。"""
    rows = (await db.execute(
        select(
            func.date(OperatingExpense.occurred_at).label("day"),
            func.coalesce(func.sum(OperatingExpense.amount), 0.0).label("total"),
        ).where(
            OperatingExpense.deleted_at.is_(None),
            OperatingExpense.occurred_at >= start,
            OperatingExpense.occurred_at <= end,
        ).group_by(func.date(OperatingExpense.occurred_at))
    )).all()
    return {r.day: float(r.total or 0) for r in rows}


async def _trade_monthly_agg(
    db: AsyncSession, start: datetime, end: datetime, channel: Optional[str] = None
) -> dict[str, dict]:
    """SQL GROUP BY strftime('%Y-%m', trade_at)，返回 {"YYYY-MM": {income,cost,profit,count}}。
    channel 非空时仅统计指定销售渠道。"""
    stmt = (
        select(
            func.strftime("%Y-%m", Transaction.trade_at).label("month"),
            func.coalesce(func.sum(Transaction.sale_price), 0.0).label("income"),
            func.coalesce(func.sum(Transaction.cost_price), 0.0).label("cost"),
            func.coalesce(func.sum(Transaction.profit), 0.0).label("profit"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.status != "closed",
            Transaction.trade_at >= start,
            Transaction.trade_at <= end,
        )
        .group_by(func.strftime("%Y-%m", Transaction.trade_at))
    )
    if channel is not None:
        stmt = stmt.where(Transaction.channel == channel)
    rows = (await db.execute(stmt)).all()
    return {
        r.month: {
            "income": float(r.income or 0),
            "cost": float(r.cost or 0),
            "profit": float(r.profit or 0),
            "count": r.count,
        }
        for r in rows
    }


async def _expense_monthly_agg(
    db: AsyncSession, start: datetime, end: datetime
) -> dict[str, float]:
    """SQL GROUP BY strftime('%Y-%m', occurred_at)，返回 {"YYYY-MM": total_amount}。"""
    rows = (await db.execute(
        select(
            func.strftime("%Y-%m", OperatingExpense.occurred_at).label("month"),
            func.coalesce(func.sum(OperatingExpense.amount), 0.0).label("total"),
        ).where(
            OperatingExpense.deleted_at.is_(None),
            OperatingExpense.occurred_at >= start,
            OperatingExpense.occurred_at <= end,
        ).group_by(func.strftime("%Y-%m", OperatingExpense.occurred_at))
    )).all()
    return {r.month: float(r.total or 0) for r in rows}


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


# ==================== 业务查询函数 ====================

async def get_finance_overview(
    db: AsyncSession, *, month: bool = True, channel: Optional[str] = None
) -> dict:
    """收支总览（本月 / 全部）。复刻 getFinanceOverview 的本月口径。
    channel 非空时仅统计指定销售渠道。"""
    now = now_utc()
    if month:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start = (start - timedelta(days=1)).replace(day=1)
        prev_end = start - timedelta(microseconds=1)
    else:
        start = datetime(1970, 1, 1)
        prev_start = datetime(1970, 1, 1)
        prev_end = datetime(1970, 1, 1)

    cur = await _trade_agg_between(db, start, now, channel)
    prev = await _trade_agg_between(db, prev_start, prev_end, channel) if month else {
        "income": 0.0, "cost": 0.0, "profit": 0.0, "count": 0,
    }

    if month:
        cur_expense = await _sum_expenses_between(db, start, now)
        prev_expense = await _sum_expenses_between(db, prev_start, prev_end)
    else:
        cur_expense = 0.0
        prev_expense = 0.0

    return build_overview(
        cur,
        prev,
        cur_expense=cur_expense,
        prev_expense=prev_expense,
    )


async def get_product_profit_stats(
    db: AsyncSession,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    channel: Optional[str] = None,
) -> list[dict]:
    """商品利润排行。可选按 trade_at 范围过滤，可选按 channel 过滤。"""
    rows = await _product_agg_between(db, start, end, channel)
    return build_product_profit_stats(rows)


async def get_customer_value_stats(db: AsyncSession, limit: int = 100) -> list[dict]:
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


async def get_finance_overview_by_range(
    db: AsyncSession, start: datetime, end: datetime, channel: Optional[str] = None
) -> dict:
    """自定义时间范围收支总览，环比 = 上一同等长度周期。
    channel 非空时仅统计指定销售渠道。"""
    cur = await _trade_agg_between(db, start, end, channel)
    duration = end - start
    prev_end = start - timedelta(microseconds=1)
    prev_start = prev_end - duration
    prev = await _trade_agg_between(db, prev_start, prev_end, channel)
    cur_expense = await _sum_expenses_between(db, start, end)
    prev_expense = await _sum_expenses_between(db, prev_start, prev_end)
    return build_overview(
        cur,
        prev,
        cur_expense=cur_expense,
        prev_expense=prev_expense,
    )


async def get_trend(
    db: AsyncSession, days: int = 30, channel: Optional[str] = None
) -> list[dict]:
    """近 N 天每日收支趋势（复刻前端 getTrend）。
    channel 非空时仅统计指定销售渠道。"""
    end = now_utc()
    start = (end - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    trade_buckets = await _trade_daily_agg(db, start, end, channel)
    expense_buckets = await _expense_daily_agg(db, start, end)
    return build_daily_trend(trade_buckets, expense_buckets, start, end)


async def get_monthly_comparison(
    db: AsyncSession, months: int = 6, channel: Optional[str] = None
) -> list[dict]:
    """近 N 月对比（复刻前端 getMonthlyComparison）。
    channel 非空时仅统计指定销售渠道。"""
    now = now_utc()
    # 精确算到 months 个月前的月初
    y, m = now.year, now.month
    for _ in range(months - 1):
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    start = datetime(y, m, 1)
    trade_buckets = await _trade_monthly_agg(db, start, now, channel)
    expense_buckets = await _expense_monthly_agg(db, start, now)
    return build_monthly_comparison(
        trade_buckets,
        expense_buckets,
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


async def get_channel_breakdown(
    db: AsyncSession, start: datetime, end: datetime
) -> list[dict]:
    """按销售渠道 GROUP BY 聚合，返回 [{channel, income, cost, profit, count}, ...]。
    用于财务报表渠道占比展示。排除 closed/deleted 交易。"""
    rows = (await db.execute(
        select(
            Transaction.channel.label("channel"),
            func.coalesce(func.sum(Transaction.sale_price), 0.0).label("income"),
            func.coalesce(func.sum(Transaction.cost_price), 0.0).label("cost"),
            func.coalesce(func.sum(Transaction.profit), 0.0).label("profit"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.status != "closed",
            Transaction.trade_at >= start,
            Transaction.trade_at <= end,
        )
        .group_by(Transaction.channel)
    )).all()
    return [
        {
            "channel": r.channel,
            "income": float(r.income or 0),
            "cost": float(r.cost or 0),
            "profit": float(r.profit or 0),
            "count": r.count,
        }
        for r in rows
    ]
