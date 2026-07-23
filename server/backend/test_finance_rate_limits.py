"""finance 与 expenses 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. finance 路由 7 个 GET 读端点 + 1 个 POST 写端点（backfill-cost）均挂载 @limiter.limit
2. expenses 路由 GET 读端点 100/min，POST/PATCH/DELETE 写端点 30/min
3. 装饰器限流值与 project_memory 约束一致
4. 实际触发：超过限额返回 429
"""
import unittest

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.security import token as token_module
from app.security.rate_limit import limiter


def _get_route_limit(module_path: str) -> str | None:
    """从 limiter._route_limits 中读取已注册的限流值。

    slowapi 把 @limiter.limit 装饰器信息存到 limiter._route_limits 字典，
    键为 "app.routers.<module>.<function>"，值为 Limit 对象列表。
    返回 str(limit)（如 "100 per 1 minute"），未注册时返回 None。
    """
    limits = limiter._route_limits.get(module_path)
    if not limits:
        return None
    return str(limits[0].limit)


def _assert_rate_limit(testcase, module_path: str, expected: str):
    """断言指定端点已挂载指定限流值。

    expected 是限流值的子串（如 "100"、"3"、"30"），用于匹配 "100 per 1 minute" 等格式。
    """
    actual = _get_route_limit(module_path)
    testcase.assertIsNotNone(
        actual,
        f"{module_path} 未挂载 @limiter.limit 装饰器",
    )
    testcase.assertIn(
        expected,
        actual,
        f"{module_path} 限流值不匹配：期望含 {expected}，实际 {actual}",
    )
    testcase.assertIn(
        "minute",
        actual,
        f"{module_path} 限流单位应为 minute（项目约束：req/min/IP），实际 {actual}",
    )


class FinanceRouteRateLimitDecorationTests(unittest.TestCase):
    """finance 路由所有端点必须挂载 @limiter.limit。"""

    def test_all_finance_read_endpoints_limited_to_100_per_minute(self):
        for fn_name in [
            "finance_overview",
            "product_profit_stats",
            "customer_value_stats",
            "finance_overview_by_range",
            "trend",
            "monthly_comparison",
            "channel_breakdown",
            "new_customer_count",
        ]:
            _assert_rate_limit(
                self,
                f"app.routers.finance.{fn_name}",
                "100",
            )

    def test_finance_backfill_cost_endpoint_limited_to_3_per_minute(self):
        """backfill-cost 是写操作 + 全表扫描 + 客户统计重算，限流更严格。"""
        _assert_rate_limit(
            self,
            "app.routers.finance.backfill_cost",
            "3",
        )


class ExpensesRouteRateLimitDecorationTests(unittest.TestCase):
    """expenses 路由：读 100/min，写 30/min。"""

    def test_expenses_list_limited_to_100_per_minute(self):
        _assert_rate_limit(self, "app.routers.expenses.list_expenses", "100")

    def test_expenses_write_endpoints_limited_to_30_per_minute(self):
        for fn_name in ["create_expense", "update_expense", "delete_expense"]:
            _assert_rate_limit(self, f"app.routers.expenses.{fn_name}", "30")


@pytest.mark.rate_limit
class FinanceRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 finance 限额返回 429。"""

    async def asyncSetUp(self):
        # 提供内存数据库，避免访问真实 SQLite
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "rate-limit-test-token-finance"
        try:
            limiter._storage.reset()
        except Exception:
            pass

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()
        token_module.get_api_token = self._original_get
        try:
            limiter._storage.reset()
        except Exception:
            pass

    async def test_finance_overview_returns_429_on_101st_request(self):
        """finance 读端点限流 100/min：第 101 次应返回 429。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(100):
                resp = await client.get("/api/finance/overview")
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.get("/api/finance/overview")
            self.assertEqual(resp.status_code, 429)

    async def test_finance_backfill_cost_returns_429_on_4th_request(self):
        """backfill-cost 限流 3/min：第 4 次应返回 429。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(3):
                resp = await client.post("/api/finance/backfill-cost")
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.post("/api/finance/backfill-cost")
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
