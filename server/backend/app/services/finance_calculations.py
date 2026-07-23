"""Database-independent finance calculations.

build_* 函数接收 SQL 聚合结果（dict / 命名行），做格式化（round2/环比/补零），
不直接依赖 ORM 对象或数据库连接。
"""
from datetime import datetime, timedelta
from typing import Any

from ..utils.helpers import round2


def month_range(date: datetime) -> tuple[datetime, datetime]:
    start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if date.month == 12:
        end = start.replace(year=date.year + 1, month=1) - timedelta(microseconds=1)
    else:
        end = start.replace(month=date.month + 1) - timedelta(microseconds=1)
    return start, end


def _change(current: float, previous: float) -> float:
    if previous == 0:
        return 1.0 if current > 0 else 0.0
    return round2((current - previous) / previous)


def build_overview(
    current: dict[str, float],
    previous: dict[str, float],
    *,
    cur_expense: float = 0.0,
    prev_expense: float = 0.0,
) -> dict:
    """构建收支总览。current/previous 为 SQL 聚合结果 {income, cost, profit, count}。"""
    total_income = round2(current["income"])
    total_cost = round2(current["cost"] + cur_expense)
    total_profit = round2(total_income - total_cost)
    prev_income = round2(previous["income"])
    prev_cost = round2(previous["cost"] + prev_expense)
    prev_profit = round2(prev_income - prev_cost)
    return {
        "totalIncome": total_income,
        "totalCost": total_cost,
        "totalProfit": total_profit,
        "operatingExpense": cur_expense,
        "profitRate": round2(total_profit / total_income) if total_income > 0 else 0.0,
        "tradeCount": current["count"],
        "prevIncome": prev_income,
        "prevProfit": prev_profit,
        "prevTradeCount": previous["count"],
        "incomeChange": _change(total_income, prev_income),
        "profitChange": _change(total_profit, prev_profit),
        "tradeCountChange": _change(current["count"], previous["count"]),
    }


def build_product_profit_stats(rows: Any) -> list[dict]:
    """构建商品利润排行。rows 为 SQL GROUP BY 结果（具名行，含 product_name/income/cost/profit/count）。"""
    result = [
        {
            "productName": row.product_name,
            "totalIncome": round2(float(row.income or 0)),
            "totalCost": round2(float(row.cost or 0)),
            "totalProfit": round2(float(row.profit or 0)),
            "count": row.count,
            "profitRate": (
                round2(float(row.profit or 0) / float(row.income))
                if row.income and float(row.income) > 0
                else 0.0
            ),
        }
        for row in rows
    ]
    result.sort(key=lambda row: row["totalProfit"], reverse=True)
    return result


def build_daily_trend(
    trade_buckets: dict[str, dict[str, float]],
    expense_buckets: dict[str, float],
    start: datetime,
    end: datetime,
) -> list[dict]:
    """构建每日收支趋势。trade_buckets/expense_buckets 为 SQL GROUP BY DATE 结果的 dict 映射。
    Python 仅负责补零天（SQL GROUP BY 只返回有数据的天）。
    """
    series: list[str] = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    last = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= last:
        series.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return [
        {
            "date": day,
            "income": round2(trade_buckets.get(day, {}).get("income", 0.0)),
            "cost": round2(
                trade_buckets.get(day, {}).get("cost", 0.0)
                + expense_buckets.get(day, 0.0)
            ),
            "profit": round2(
                trade_buckets.get(day, {}).get("profit", 0.0)
                - expense_buckets.get(day, 0.0)
            ),
        }
        for day in series
    ]


def build_monthly_comparison(
    trade_buckets: dict[str, dict[str, float]],
    expense_buckets: dict[str, float],
    *,
    start_year: int,
    start_month: int,
    months: int,
) -> list[dict]:
    """构建月度对比。trade_buckets/expense_buckets 为 SQL GROUP BY strftime(trade_at,'%Y-%m') 结果的 dict 映射。
    Python 仅负责补零月。
    """
    order: list[str] = []
    year, month = start_year, start_month
    for _ in range(months):
        key = f"{year:04d}-{month:02d}"
        order.append(key)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return [
        {
            "month": f"{int(key.split('-')[1])}月",
            "income": round2(trade_buckets.get(key, {}).get("income", 0.0)),
            "cost": round2(
                trade_buckets.get(key, {}).get("cost", 0.0)
                + expense_buckets.get(key, 0.0)
            ),
            "profit": round2(
                trade_buckets.get(key, {}).get("profit", 0.0)
                - expense_buckets.get(key, 0.0)
            ),
            "tradeCount": int(trade_buckets.get(key, {}).get("count", 0)),
        }
        for key in order
    ]
