"""customers 路由 404 语义测试。

验证 project_memory 硬约束「资源不存在返回 404」对齐 expenses/mail_record/aftersales/warranty：

1. GET /api/customers/{id} 客户不存在 → 404（原有行为，回归验证）
2. PATCH /api/customers/{id} 客户不存在 → 404（不返回 400）
3. DELETE /api/customers/{id} 客户不存在 → 404（不返回 400）
4. POST /api/customers/{id}/toggle-blacklist 客户不存在 → 404（不返回 400）
5. PATCH /api/customers/{id} 客户不存在 + expected_version → 404（404 优先于 409）
"""
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class CustomersRoute404Tests(unittest.IsolatedAsyncioTestCase):
    """customers 路由：客户不存在返回 404（对齐 expenses/mail_record/aftersales/warranty）。"""

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

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def test_get_nonexistent_customer_returns_404(self):
        """GET /api/customers/{id} 客户不存在 → 404（回归验证）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/customers/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_update_nonexistent_customer_returns_404(self):
        """PATCH /api/customers/{id} 客户不存在 → 404（不返回 400）。"""
        payload = {"xianyu_nickname": "新昵称"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch("/api/customers/9999", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_delete_nonexistent_customer_returns_404(self):
        """DELETE /api/customers/{id} 客户不存在 → 404（不返回 400）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/api/customers/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_toggle_blacklist_nonexistent_customer_returns_404(self):
        """POST /api/customers/{id}/toggle-blacklist 客户不存在 → 404（不返回 400）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/customers/9999/toggle-blacklist")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_update_nonexistent_customer_404_wins_over_409(self):
        """PATCH 不存在客户 + expected_version → 404（404 优先于 409 ConcurrencyError）。

        验证 update_customer 中「客户不存在」检查在乐观锁检查之前，
        ConcurrencyError 不会先抛。
        """
        payload = {"expected_version": 5}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch("/api/customers/9999", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
