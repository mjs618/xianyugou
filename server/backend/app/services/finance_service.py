"""财务统计聚合服务 - 复刻前端 financeService.ts（只读聚合）。"""
from datetime import datetime, timedelta
from typing import Optional
import calendar
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, RebateRecord, Customer, OperatingExpense
from ..utils.helpers import round2, now_utc


def _month_range(date: datetime) -> tuple[datetime, datetime]:
    """本月起止（含）。"""
    start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 下月 1 号 - 1 微秒
    if date.month == 12:
        end = start.replace(year=date.year + 1, month=1) - timedelta(microseconds=1)
    else:
        end = start.replace(month=date.month + 1) - timedelta(microseconds=1)
    return start, end


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

    total_income = round2(sum(t.sale_price for t in cur_trades))
    total_cost = round2(sum(t.cost_price for t in cur_trades) + cur_expense)
    total_profit = round2(total_income - total_cost)
    profit_rate = round2(total_profit / total_income) if total_income > 0 else 0.0
    prev_income = round2(sum(t.sale_price for t in prev_trades))
    prev_cost = round2(sum(t.cost_price for t in prev_trades) + prev_expense)
    prev_profit = round2(prev_income - prev_cost)
    prev_count = len(prev_trades)

    def _change(cur: float, prev: float) -> float:
        if prev == 0:
            return 1.0 if cur > 0 else 0.0
        return round2((cur - prev) / prev)

    return {
        "totalIncome": total_income,
        "totalCost": total_cost,
        "totalProfit": total_profit,
        "operatingExpense": cur_expense,
        "profitRate": profit_rate,
        "tradeCount": len(cur_trades),
        "prevIncome": prev_income,
        "prevProfit": prev_profit,
        "prevTradeCount": prev_count,
        "incomeChange": _change(total_income, prev_income),
        "profitChange": _change(total_profit, prev_profit),
        "tradeCountChange": _change(len(cur_trades), prev_count),
    }


async def get_product_profit_stats(db: AsyncSession, start: Optional[datetime] = None, end: Optional[datetime] = None) -> list[dict]:
    """商品利润排行。可选按 trade_at 范围过滤。"""
    stmt = select(Transaction).where(Transaction.deleted_at.is_(None))
    if start is not None:
        stmt = stmt.where(Transaction.trade_at >= start)
    if end is not None:
        stmt = stmt.where(Transaction.trade_at <= end)
    trades = list((await db.execute(stmt)).scalars().all())
    agg: dict[str, dict] = {}
    for t in trades:
        d = agg.setdefault(t.product_name, {"income": 0.0, "profit": 0.0, "count": 0})
        d["income"] += t.sale_price
        d["profit"] += t.profit
        d["count"] += 1
    result = []
    for name, d in agg.items():
        result.append({
            "productName": name,
            "totalIncome": round2(d["income"]),
            "totalProfit": round2(d["profit"]),
            "count": d["count"],
            "profitRate": round2(d["profit"] / d["income"]) if d["income"] > 0 else 0.0,
        })
    result.sort(key=lambda x: x["totalProfit"], reverse=True)
    return result


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


def _build_overview(
    cur: list[Transaction],
    prev: list[Transaction],
    *,
    cur_expense: float = 0.0,
    prev_expense: float = 0.0,
) -> dict:
    """从两段交易列表构建 overview（复刻前端 buildOverview）。"""
    total_income = round2(sum(t.sale_price for t in cur))
    total_cost = round2(sum(t.cost_price for t in cur) + cur_expense)
    total_profit = round2(total_income - total_cost)
    prev_income = round2(sum(t.sale_price for t in prev))
    prev_cost = round2(sum(t.cost_price for t in prev) + prev_expense)
    prev_profit = round2(prev_income - prev_cost)
    prev_count = len(prev)

    def _change(c: float, p: float) -> float:
        if p == 0:
            return 1.0 if c > 0 else 0.0
        return round2((c - p) / p)

    return {
        "totalIncome": total_income,
        "totalCost": total_cost,
        "totalProfit": total_profit,
        "operatingExpense": cur_expense,
        "profitRate": round2(total_profit / total_income) if total_income > 0 else 0.0,
        "tradeCount": len(cur),
        "prevIncome": prev_income,
        "prevProfit": prev_profit,
        "prevTradeCount": prev_count,
        "incomeChange": _change(total_income, prev_income),
        "profitChange": _change(total_profit, prev_profit),
        "tradeCountChange": _change(len(cur), prev_count),
    }


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
    return _build_overview(cur, prev, cur_expense=cur_expense, prev_expense=prev_expense)


async def get_trend(db: AsyncSession, days: int = 30) -> list[dict]:
    """近 N 天每日收支趋势（复刻前端 getTrend）。"""
    end = now_utc()
    start = (end - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    trades = await _trades_between(db, start, end)
    expenses = await _expenses_between(db, start, end)
    # 构建日期序列
    series: list[str] = []
    cur_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
    last_date = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while cur_date <= last_date:
        series.append(cur_date.strftime("%Y-%m-%d"))
        cur_date += timedelta(days=1)
    bucket = {d: {"income": 0.0, "cost": 0.0, "profit": 0.0} for d in series}
    for t in trades:
        key = t.trade_at.strftime("%Y-%m-%d") if t.trade_at else None
        if key and key in bucket:
            bucket[key]["income"] += t.sale_price
            bucket[key]["cost"] += t.cost_price
            bucket[key]["profit"] += t.profit
    for expense in expenses:
        key = expense.occurred_at.strftime("%Y-%m-%d") if expense.occurred_at else None
        if key and key in bucket:
            bucket[key]["cost"] += expense.amount
            bucket[key]["profit"] -= expense.amount
    return [{"date": d, "income": round2(v["income"]), "cost": round2(v["cost"]), "profit": round2(v["profit"])} for d, v in zip(series, [bucket[d] for d in series])]


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
    bucket: dict[str, dict] = {}
    keys_order: list[str] = []
    cy, cm = y, m
    for _ in range(months):
        k = f"{cy:04d}-{cm:02d}"
        bucket[k] = {"income": 0.0, "cost": 0.0, "profit": 0.0, "count": 0}
        keys_order.append(k)
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1
    for t in trades:
        if not t.trade_at:
            continue
        k = t.trade_at.strftime("%Y-%m")
        if k in bucket:
            bucket[k]["income"] += t.sale_price
            bucket[k]["cost"] += t.cost_price
            bucket[k]["profit"] += t.profit
            bucket[k]["count"] += 1
    for expense in expenses:
        if not expense.occurred_at:
            continue
        k = expense.occurred_at.strftime("%Y-%m")
        if k in bucket:
            bucket[k]["cost"] += expense.amount
            bucket[k]["profit"] -= expense.amount
    return [
        {
            "month": f"{int(k.split('-')[1])}月",
            "income": round2(bucket[k]["income"]),
            "cost": round2(bucket[k]["cost"]),
            "profit": round2(bucket[k]["profit"]),
            "tradeCount": bucket[k]["count"],
        }
        for k in keys_order
    ]


async def get_new_customer_count(db: AsyncSession, date: Optional[datetime] = None) -> int:
    """本月新客户数（first_trade_at 在本月）。"""
    d = date or now_utc()
    start, end = _month_range(d)
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
