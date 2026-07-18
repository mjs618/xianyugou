"""warranty 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」：

1. GET /api/warranty/active|urgent|expired|all|{id}/extensions 读端点 100/min
2. POST /api/warranty/{id}/extend 写端点 30/min
3. POST /api/warranty/{id}/end-early 写端点 30/min
4. 实际触发：超过写端点限额返回 429
"""
import unittest
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Customer, Transaction
from app.security import token as token_module
from app.security.rate_limit import limiter
from app.utils.helpers import now_utc


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


class WarrantyRouteRateLimitDecorationTests(unittest.TestCase):
    """warranty 路由所有端点必须挂载 @limiter.limit。"""

    def test_warranty_read_endpoints_limited_to_100_per_minute(self):
        for fn_name in [
            "active",
            "urgent",
            "expired",
            "all_warranty",
            "extensions",
        ]:
            _assert_rate_limit(self, f"app.routers.warranty.{fn_name}", "100")

    def test_warranty_write_endpoints_limited_to_30_per_minute(self):
        for fn_name in ["extend", "end_early"]:
            _assert_rate_limit(self, f"app.routers.warranty.{fn_name}", "30")


@pytest.mark.rate_limit
class WarrantyRateLimit429Tests(unittest.IsolatedAsyncioTestCase):
    """实测：超过 warranty 写端点限额返回 429。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        # 预创建 customer + transaction（带未来 warranty_end），使 extend 前 30 次成功
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
                warranty_end=now_utc() + timedelta(days=30),
                channel="xianyu",
            ))
            await db.commit()

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "rate-limit-test-token-warranty"
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

    async def test_extend_warranty_returns_429_on_31st_request(self):
        """POST /api/warranty/{id}/extend 限流 30/min：第 31 次应返回 429。"""
        payload = {"days": 1, "reason": "测试延长"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(30):
                resp = await client.post("/api/warranty/1/extend", json=payload)
                self.assertNotEqual(resp.status_code, 429)
            resp = await client.post("/api/warranty/1/extend", json=payload)
            self.assertEqual(resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()
