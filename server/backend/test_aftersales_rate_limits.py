"""aftersales 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. GET /api/aftersales（含 by-transaction/stats/top-issues/{id}）读端点 100/min
2. POST /api/aftersales 写端点 30/min
3. PATCH /api/aftersales/{id} 写端点 30/min
4. DELETE /api/aftersales/{id} 写端点 30/min
5. 实际触发：超过写端点限额返回 429
"""
import unittest
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Customer, Transaction
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


class AftersalesRouteRateLimitDecorationTests(unittest.TestCase):
    """aftersales 路由所有端点必须挂载 @limiter.limit。"""

    def test_aftersales_read_endpoints_limited_to_100_per_minute(self):
        for fn_name in [
            "list_aftersales",
            "by_transaction",
            "stats",
            "top_issues",
            "get_aftersales",
        ]:
            _assert_rate_limit(self, f"app.routers.aftersales.{fn_name}", "100")

    def test_aftersales_write_endpoints_limited_to_30_per_minute(self):
        for fn_name in [
            "create_aftersales",
            "update_aftersales",
            "delete_aftersales",
        ]:
            _assert_rate_limit(self, f"app.routers.aftersales.{fn_name}", "30")


@pytest.mark.rate_limit
class AftersalesRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 aftersales 写端点限额返回 429。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        # 预创建 customer + transaction，使 POST 前 30 次成功返回 200
        async with self.Session() as db:
            db.add(Customer(id=1, xianyu_nickname="测试客户"))
            db.add(Transaction(
                id=1,
                customer_id=1,
                product_name="测试商品",
                sale_price=100.0,
                cost_price=50.0,
                profit=50.0,
                trade_at=datetime(2026, 7, 1, 10, 0, 0),
                status="completed",
                warranty_days=30,
                channel="xianyu",
            ))
            await db.commit()

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "rate-limit-test-token-aftersales"
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

    async def test_create_aftersales_returns_429_on_31st_request(self):
        """POST /api/aftersales 限流 30/min：第 31 次应返回 429。"""
        payload = {
            "transaction_id": 1,
            "issue_desc": "测试问题",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(30):
                resp = await client.post("/api/aftersales", json=payload)
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.post("/api/aftersales", json=payload)
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
