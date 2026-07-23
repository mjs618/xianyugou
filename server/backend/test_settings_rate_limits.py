"""settings 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. GET /api/settings 读端点 100/min（返回含解密 smtp_pass 的敏感数据）
2. PUT /api/settings 写端点 30/min
3. 实际触发：超过写端点限额返回 429
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


class SettingsRouteRateLimitDecorationTests(unittest.TestCase):
    """settings 路由所有端点必须挂载 @limiter.limit。"""

    def test_settings_read_endpoints_limited_to_100_per_minute(self):
        _assert_rate_limit(self, "app.routers.settings.get_settings", "100")

    def test_settings_write_endpoints_limited_to_30_per_minute(self):
        _assert_rate_limit(self, "app.routers.settings.update_settings", "30")


@pytest.mark.rate_limit
class SettingsRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 settings 写端点限额返回 429。"""

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
        token_module.get_api_token = lambda: "rate-limit-test-token-settings"
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

    async def test_update_settings_returns_429_on_31st_request(self):
        """PUT /api/settings 限流 30/min：第 31 次应返回 429。

        用 recall_days=7（合法值）避免 400 干扰，前 30 次成功返回 200，
        第 31 次触发 429。
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(30):
                resp = await client.put("/api/settings", json={"recall_days": 7})
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.put("/api/settings", json={"recall_days": 7})
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
