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


def agg_row(name, income, cost, profit, count):
    """模拟 SQL GROUP BY 命名行（product profit stats）。"""
    return SimpleNamespace(
        product_name=name,
        income=income,
        cost=cost,
        profit=profit,
        count=count,
    )


class FinanceCalculationTests(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.find_spec(MODULE_NAME)
        self.assertIsNotNone(spec, "finance_calculations module must exist")
        module = importlib.import_module(MODULE_NAME)
        self.assertEqual(PUBLIC_FUNCTIONS - set(vars(module)), set())
        return module

    def test_builds_overview_and_zero_base_changes(self):
        module = self.load_module()
        current = {"income": 100, "cost": 30, "profit": 70, "count": 1}
        previous = {"income": 0, "cost": 0, "profit": 0, "count": 0}

        result = module.build_overview(current, previous, cur_expense=6)

        self.assertEqual(result["totalIncome"], 100)
        self.assertEqual(result["totalCost"], 36)
        self.assertEqual(result["totalProfit"], 64)
        self.assertEqual(result["operatingExpense"], 6)
        self.assertEqual(result["incomeChange"], 1.0)
        self.assertEqual(result["tradeCountChange"], 1.0)

    def test_aggregates_product_profit_and_sorts_descending(self):
        module = self.load_module()
        rows = [
            agg_row("A", 150, 50, 100, 2),
            agg_row("B", 200, 150, 50, 1),
        ]

        result = module.build_product_profit_stats(rows)

        self.assertEqual([row["productName"] for row in result], ["A", "B"])
        self.assertEqual(result[0]["totalIncome"], 150)
        self.assertEqual(result[0]["totalCost"], 50)
        self.assertEqual(result[0]["totalProfit"], 100)
        self.assertEqual(result[0]["count"], 2)
        # 第二行成本字段也要正确透传
        self.assertEqual(result[1]["totalCost"], 150)

    def test_builds_continuous_daily_trend_with_expense(self):
        module = self.load_module()
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 3, 23, 59, 59)

        trade_buckets = {
            "2026-01-02": {"income": 100, "cost": 30, "profit": 70, "count": 1},
        }
        expense_buckets = {"2026-01-02": 6}

        result = module.build_daily_trend(trade_buckets, expense_buckets, start, end)

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

        trade_buckets = {
            "2026-01": {"income": 100, "cost": 30, "profit": 70, "count": 1},
        }
        expense_buckets = {"2026-01": 6}

        result = module.build_monthly_comparison(
            trade_buckets,
            expense_buckets,
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

    def test_finance_service_excludes_closed_transactions(self):
        """回归守卫：finance_service.py 所有 Transaction 查询必须排除 status='closed' 交易。

        对应设计规范「全额退款成功 → 净收入归零」。
        通过源码扫描验证：每个包含 Transaction.deleted_at.is_(None) 的查询
        也必须包含 Transaction.status != "closed" 过滤。
        """
        source = SERVICE_PATH.read_text(encoding="utf-8")
        # 每个 Transaction 查询都包含 deleted_at.is_(None)，以此作为查询数代理
        tx_query_count = source.count("Transaction.deleted_at.is_(None)")
        # 统计 status != "closed" 过滤条件出现次数
        closed_filter_count = source.count('Transaction.status != "closed"')
        self.assertGreaterEqual(
            closed_filter_count,
            tx_query_count,
            f"finance_service.py 有 {tx_query_count} 处 Transaction 查询（含 deleted_at.is_(None)），"
            f"但只有 {closed_filter_count} 处排除了 closed 状态",
        )


if __name__ == "__main__":
    unittest.main()
