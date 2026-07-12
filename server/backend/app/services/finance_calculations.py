"""Database-independent finance calculations."""
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
    current: list[Any],
    previous: list[Any],
    *,
    cur_expense: float = 0.0,
    prev_expense: float = 0.0,
) -> dict:
    total_income = round2(sum(item.sale_price for item in current))
    total_cost = round2(sum(item.cost_price for item in current) + cur_expense)
    total_profit = round2(total_income - total_cost)
    prev_income = round2(sum(item.sale_price for item in previous))
    prev_cost = round2(sum(item.cost_price for item in previous) + prev_expense)
    prev_profit = round2(prev_income - prev_cost)
    return {
        "totalIncome": total_income,
        "totalCost": total_cost,
        "totalProfit": total_profit,
        "operatingExpense": cur_expense,
        "profitRate": round2(total_profit / total_income) if total_income > 0 else 0.0,
        "tradeCount": len(current),
        "prevIncome": prev_income,
        "prevProfit": prev_profit,
        "prevTradeCount": len(previous),
        "incomeChange": _change(total_income, prev_income),
        "profitChange": _change(total_profit, prev_profit),
        "tradeCountChange": _change(len(current), len(previous)),
    }


def build_product_profit_stats(trades: list[Any]) -> list[dict]:
    aggregated: dict[str, dict] = {}
    for item in trades:
        row = aggregated.setdefault(
            item.product_name,
            {"income": 0.0, "profit": 0.0, "count": 0},
        )
        row["income"] += item.sale_price
        row["profit"] += item.profit
        row["count"] += 1
    result = [
        {
            "productName": name,
            "totalIncome": round2(row["income"]),
            "totalProfit": round2(row["profit"]),
            "count": row["count"],
            "profitRate": (
                round2(row["profit"] / row["income"])
                if row["income"] > 0
                else 0.0
            ),
        }
        for name, row in aggregated.items()
    ]
    result.sort(key=lambda row: row["totalProfit"], reverse=True)
    return result


def build_daily_trend(
    trades: list[Any],
    expenses: list[Any],
    start: datetime,
    end: datetime,
) -> list[dict]:
    series: list[str] = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    last = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= last:
        series.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    buckets = {
        day: {"income": 0.0, "cost": 0.0, "profit": 0.0}
        for day in series
    }
    for item in trades:
        key = item.trade_at.strftime("%Y-%m-%d") if item.trade_at else None
        if key in buckets:
            buckets[key]["income"] += item.sale_price
            buckets[key]["cost"] += item.cost_price
            buckets[key]["profit"] += item.profit
    for item in expenses:
        key = item.occurred_at.strftime("%Y-%m-%d") if item.occurred_at else None
        if key in buckets:
            buckets[key]["cost"] += item.amount
            buckets[key]["profit"] -= item.amount
    return [
        {
            "date": day,
            "income": round2(buckets[day]["income"]),
            "cost": round2(buckets[day]["cost"]),
            "profit": round2(buckets[day]["profit"]),
        }
        for day in series
    ]


def build_monthly_comparison(
    trades: list[Any],
    expenses: list[Any],
    *,
    start_year: int,
    start_month: int,
    months: int,
) -> list[dict]:
    buckets: dict[str, dict] = {}
    order: list[str] = []
    year, month = start_year, start_month
    for _ in range(months):
        key = f"{year:04d}-{month:02d}"
        buckets[key] = {
            "income": 0.0,
            "cost": 0.0,
            "profit": 0.0,
            "count": 0,
        }
        order.append(key)
        month += 1
        if month > 12:
            month = 1
            year += 1
    for item in trades:
        if item.trade_at:
            key = item.trade_at.strftime("%Y-%m")
            if key in buckets:
                buckets[key]["income"] += item.sale_price
                buckets[key]["cost"] += item.cost_price
                buckets[key]["profit"] += item.profit
                buckets[key]["count"] += 1
    for item in expenses:
        if item.occurred_at:
            key = item.occurred_at.strftime("%Y-%m")
            if key in buckets:
                buckets[key]["cost"] += item.amount
                buckets[key]["profit"] -= item.amount
    return [
        {
            "month": f"{int(key.split('-')[1])}月",
            "income": round2(buckets[key]["income"]),
            "cost": round2(buckets[key]["cost"]),
            "profit": round2(buckets[key]["profit"]),
            "tradeCount": buckets[key]["count"],
        }
        for key in order
    ]
