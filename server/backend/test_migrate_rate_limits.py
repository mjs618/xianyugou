"""migrate 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. GET /api/migrate/export 读端点 100/min
2. POST /api/migrate/import 写端点 3/minute（数据覆盖操作，同 system/restore）
3. 实际触发：超过 import 限额返回 429
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


class MigrateRouteRateLimitDecorationTests(unittest.TestCase):
    """migrate 路由所有端点必须挂载 @limiter.limit。"""

    def test_migrate_read_endpoints_limited_to_100_per_minute(self):
        _assert_rate_limit(self, "app.routers.migrate.export_backup", "100")

    def test_migrate_import_limited_to_3_per_minute(self):
        """import 是数据覆盖操作，与 system/restore 一致严格限流 3/min。"""
        _assert_rate_limit(self, "app.routers.migrate.import_backup", "3")


@pytest.mark.rate_limit
class MigrateRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 migrate import 限额返回 429。"""

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
        token_module.get_api_token = lambda: "rate-limit-test-token-migrate"
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

    async def test_import_returns_429_on_4th_request(self):
        """POST /api/migrate/import 限流 3/min：第 4 次应返回 429。

        import 是空 dict（payload 为空），会触发 ValueError → 400，
        但 429 应在 3 次成功后被触发（400 不消耗 limiter 配额）。
        """
        # 空 dict 会被 service 拒绝（400），但 slowapi 在路由前拦截，仍消耗配额
        payload = {}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(3):
                resp = await client.post("/api/migrate/import", json=payload)
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.post("/api/migrate/import", json=payload)
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
