"""rebates 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. GET /api/rebates（含 pending-count/pending-total/by-referrer/{id}/by-transaction/{id}）读端点 100/min
2. PATCH /api/rebates/{id}（写端点）30/min
3. POST /api/rebates/batch-pay（写端点）30/min
4. 实际触发：超过读端点限额返回 429
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
    """从 limiter._route_limits 中读取已注册的限流值。"""
    limits = limiter._route_limits.get(module_path)
    if not limits:
        return None
    return str(limits[0].limit)


def _assert_rate_limit(testcase, module_path: str, expected: str):
    """断言指定端点已挂载指定限流值。"""
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


class RebatesRouteRateLimitDecorationTests(unittest.TestCase):
    """rebates 路由所有端点必须挂载 @limiter.limit。"""

    def test_rebates_read_endpoints_limited_to_100_per_minute(self):
        for fn_name in [
            "list_rebates",
            "pending_count",
            "pending_total",
            "by_referrer",
            "by_transaction",
        ]:
            _assert_rate_limit(self, f"app.routers.rebates.{fn_name}", "100")

    def test_rebates_write_endpoints_limited_to_30_per_minute(self):
        for fn_name in [
            "update_rebate_status",
            "batch_pay",
        ]:
            _assert_rate_limit(self, f"app.routers.rebates.{fn_name}", "30")


@pytest.mark.rate_limit
class RebatesRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 rebates 读端点限额返回 429。"""

    async def asyncSetUp(self):
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
        token_module.get_api_token = lambda: "rate-limit-test-token-rebates"
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

    async def test_list_rebates_returns_429_on_101st_request(self):
        """GET /api/rebates 限流 100/min：第 101 次应返回 429。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(100):
                resp = await client.get("/api/rebates")
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.get("/api/rebates")
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
