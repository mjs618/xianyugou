# Finance Calculation Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract database-independent finance aggregation into a dedicated calculation module while preserving every finance API and reporting rule.

**Architecture:** `finance_calculations.py` accepts transaction/expense-like objects and returns existing response dictionaries. `finance_service.py` retains time-window orchestration and SQL queries, then delegates aggregation to the pure module.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest/unittest, Docker Compose

---

## File Structure

- Create `server/backend/app/services/finance_calculations.py`: overview, product, daily, monthly, and month-range calculations.
- Modify `server/backend/app/services/finance_service.py`: keep queries and delegate calculations.
- Create `server/backend/test_finance_calculations.py`: pure behavior and dependency-boundary tests.
- Do not modify the already-dirty `server/backend/test_expense_finance_service.py` or `server/backend/app/utils/helpers.py`.

### Task 1: Establish the calculation contract with failing tests

**Files:**
- Create: `server/backend/test_finance_calculations.py`

- [ ] **Step 1: Write the failing contract**

```python
import ast
import importlib
import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


MODULE_NAME = "app.services.finance_calculations"
MODULE_PATH = Path(__file__).parent / "app" / "services" / "finance_calculations.py"
SERVICE_PATH = Path(__file__).parent / "app" / "services" / "finance_service.py"
PUBLIC_FUNCTIONS = {
    "month_range",
    "build_overview",
    "build_product_profit_stats",
    "build_daily_trend",
    "build_monthly_comparison",
}


def trade(name, sale, cost, profit, when):
    return SimpleNamespace(product_name=name, sale_price=sale, cost_price=cost, profit=profit, trade_at=when)


def expense(amount, when):
    return SimpleNamespace(amount=amount, occurred_at=when)


class FinanceCalculationTests(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.find_spec(MODULE_NAME)
        self.assertIsNotNone(spec, "finance_calculations module must exist")
        module = importlib.import_module(MODULE_NAME)
        self.assertEqual(PUBLIC_FUNCTIONS - set(vars(module)), set())
        return module

    def test_builds_overview_and_zero_base_changes(self):
        module = self.load_module()
        current = [trade("A", 100, 30, 70, datetime(2026, 1, 2))]
        result = module.build_overview(current, [], cur_expense=6)
        self.assertEqual(result["totalIncome"], 100)
        self.assertEqual(result["totalCost"], 36)
        self.assertEqual(result["totalProfit"], 64)
        self.assertEqual(result["operatingExpense"], 6)
        self.assertEqual(result["incomeChange"], 1.0)
        self.assertEqual(result["tradeCountChange"], 1.0)

    def test_aggregates_product_profit_and_sorts_descending(self):
        module = self.load_module()
        trades = [
            trade("A", 100, 30, 70, datetime(2026, 1, 2)),
            trade("A", 50, 20, 30, datetime(2026, 1, 3)),
            trade("B", 200, 150, 50, datetime(2026, 1, 3)),
        ]
        result = module.build_product_profit_stats(trades)
        self.assertEqual([row["productName"] for row in result], ["A", "B"])
        self.assertEqual(result[0]["totalIncome"], 150)
        self.assertEqual(result[0]["totalProfit"], 100)
        self.assertEqual(result[0]["count"], 2)

    def test_builds_continuous_daily_trend_with_expense(self):
        module = self.load_module()
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 3, 23, 59, 59)
        result = module.build_daily_trend(
            [trade("A", 100, 30, 70, datetime(2026, 1, 2, 10))],
            [expense(6, datetime(2026, 1, 2, 11))],
            start,
            end,
        )
        self.assertEqual([row["date"] for row in result], ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(result[0], {"date": "2026-01-01", "income": 0.0, "cost": 0.0, "profit": 0.0})
        self.assertEqual(result[1]["cost"], 36)
        self.assertEqual(result[1]["profit"], 64)

    def test_builds_cross_year_months_and_month_range(self):
        module = self.load_module()
        result = module.build_monthly_comparison(
            [trade("A", 100, 30, 70, datetime(2026, 1, 2))],
            [expense(6, datetime(2026, 1, 2))],
            start_year=2025,
            start_month=12,
            months=3,
        )
        self.assertEqual([row["month"] for row in result], ["12月", "1月", "2月"])
        self.assertEqual(result[1]["cost"], 36)
        self.assertEqual(result[1]["profit"], 64)
        start, end = module.month_range(datetime(2025, 12, 15))
        self.assertEqual(start, datetime(2025, 12, 1))
        self.assertEqual(end, datetime(2025, 12, 31, 23, 59, 59, 999999))

    def test_module_owns_functions_without_database_dependencies(self):
        module = self.load_module()
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertLessEqual(imports, {"datetime", "typing", "utils"})
        for name in PUBLIC_FUNCTIONS:
            self.assertEqual(getattr(module, name).__module__, MODULE_NAME)
        service_tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
        service_defs = {node.name for node in service_tree.body if isinstance(node, ast.FunctionDef)}
        self.assertNotIn("_month_range", service_defs)
        self.assertNotIn("_build_overview", service_defs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest server/backend/test_finance_calculations.py -q
```

Expected: five assertion failures containing `finance_calculations module must exist`, not collection errors.

- [ ] **Step 3: Commit the RED contract only**

```powershell
git add -- server/backend/test_finance_calculations.py
git commit -m "test: define finance calculation boundary"
```

### Task 2: Implement pure calculations and reconnect the service

**Files:**
- Create: `server/backend/app/services/finance_calculations.py`
- Modify: `server/backend/app/services/finance_service.py`

- [ ] **Step 1: Create the calculation module**

Implement exactly these functions, using the existing `round2` helper:

```python
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


def build_overview(current: list[Any], previous: list[Any], *, cur_expense: float = 0.0, prev_expense: float = 0.0) -> dict:
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
        row = aggregated.setdefault(item.product_name, {"income": 0.0, "profit": 0.0, "count": 0})
        row["income"] += item.sale_price
        row["profit"] += item.profit
        row["count"] += 1
    result = [{
        "productName": name,
        "totalIncome": round2(row["income"]),
        "totalProfit": round2(row["profit"]),
        "count": row["count"],
        "profitRate": round2(row["profit"] / row["income"]) if row["income"] > 0 else 0.0,
    } for name, row in aggregated.items()]
    result.sort(key=lambda row: row["totalProfit"], reverse=True)
    return result


def build_daily_trend(trades: list[Any], expenses: list[Any], start: datetime, end: datetime) -> list[dict]:
    series: list[str] = []
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    last = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= last:
        series.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    buckets = {day: {"income": 0.0, "cost": 0.0, "profit": 0.0} for day in series}
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
    return [{"date": day, "income": round2(buckets[day]["income"]), "cost": round2(buckets[day]["cost"]), "profit": round2(buckets[day]["profit"])} for day in series]


def build_monthly_comparison(trades: list[Any], expenses: list[Any], *, start_year: int, start_month: int, months: int) -> list[dict]:
    buckets: dict[str, dict] = {}
    order: list[str] = []
    year, month = start_year, start_month
    for _ in range(months):
        key = f"{year:04d}-{month:02d}"
        buckets[key] = {"income": 0.0, "cost": 0.0, "profit": 0.0, "count": 0}
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
    return [{"month": f"{int(key.split('-')[1])}月", "income": round2(buckets[key]["income"]), "cost": round2(buckets[key]["cost"]), "profit": round2(buckets[key]["profit"]), "tradeCount": buckets[key]["count"]} for key in order]
```

- [ ] **Step 2: Reconnect `finance_service.py`**

Add explicit imports:

```python
from .finance_calculations import (
    build_daily_trend,
    build_monthly_comparison,
    build_overview,
    build_product_profit_stats,
    month_range,
)
```

Then make only these replacements:

- Remove `_month_range` and `_build_overview` definitions.
- In `get_finance_overview`, replace inline total/ratio/change construction with `return build_overview(cur_trades, prev_trades, cur_expense=cur_expense, prev_expense=prev_expense)`.
- In `get_product_profit_stats`, replace inline aggregation with `return build_product_profit_stats(trades)`.
- In `get_finance_overview_by_range`, call `build_overview`.
- In `get_trend`, replace series/bucket aggregation with `return build_daily_trend(trades, expenses, start, end)`.
- In `get_monthly_comparison`, retain the start-year/start-month calculation and return `build_monthly_comparison(trades, expenses, start_year=y, start_month=m, months=months)`.
- In `get_new_customer_count`, call `month_range(d)`.

Do not edit SQL filters, time windows, function signatures, routers, schemas, or dirty neighboring files.

- [ ] **Step 3: Verify GREEN and integration**

```powershell
python -m pytest server/backend/test_finance_calculations.py server/backend/test_expense_finance_service.py -q
```

Expected: all pure and existing integration tests pass.

- [ ] **Step 4: Verify source and dirty-worktree boundaries**

```powershell
git diff --check -- server/backend/app/services/finance_calculations.py server/backend/app/services/finance_service.py server/backend/test_finance_calculations.py
git diff --name-only
```

Expected: no whitespace errors; existing unrelated dirty paths remain present and untouched.

- [ ] **Step 5: Commit only stage 3E implementation files**

```powershell
git add -- server/backend/app/services/finance_calculations.py server/backend/app/services/finance_service.py
git commit -m "refactor: isolate finance calculations"
```

### Task 3: Full verification and runtime checks

- [ ] **Step 1: Run backend tests**

```powershell
python -m pytest server/backend -q
```

Expected: all backend tests and subtests pass, including the user's current uncommitted changes.

- [ ] **Step 2: Run frontend tests, type check, and build**

```powershell
npm test -- --run
npm run check
npm run build
```

Expected: all frontend tests pass, TypeScript check passes, and build succeeds.

- [ ] **Step 3: Rebuild backend and verify read-only endpoints**

```powershell
docker compose up -d --build backend
```

Verify `/api/health`, `/api/finance/overview`, `/api/finance/trend`, and `/openapi.json` return 200 without printing response bodies.

- [ ] **Step 4: Verify database and backup**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: current equals the packaged head and backup verification succeeds.

- [ ] **Step 5: Confirm stage files are committed and user changes remain**

```powershell
git status --short
git log -5 --oneline
```

Expected: stage 3E files are clean; all pre-existing unrelated modified/untracked files remain visible and uncommitted.
