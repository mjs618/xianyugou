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
    return SimpleNamespace(
        product_name=name,
        sale_price=sale,
        cost_price=cost,
        profit=profit,
        trade_at=when,
    )


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

        self.assertEqual(
            [row["date"] for row in result],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        self.assertEqual(
            result[0],
            {
                "date": "2026-01-01",
                "income": 0.0,
                "cost": 0.0,
                "profit": 0.0,
            },
        )
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

        self.assertEqual(
            [row["month"] for row in result],
            ["12月", "1月", "2月"],
        )
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
        service_defs = {
            node.name for node in service_tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertNotIn("_month_range", service_defs)
        self.assertNotIn("_build_overview", service_defs)


if __name__ == "__main__":
    unittest.main()
