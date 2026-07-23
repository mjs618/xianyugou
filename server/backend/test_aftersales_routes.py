"""aftersales 路由 404 语义测试。

验证 project_memory 硬约束「资源不存在返回 404」对齐 expenses/mail_record：

1. POST /api/aftersales transaction_id 不存在 → 404
2. PATCH /api/aftersales/{id} 工单不存在 → 404
3. DELETE /api/aftersales/{id} 工单不存在 → 404
4. GET /api/aftersales/{id} 工单不存在 → 404（原有行为，回归验证）
"""
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class AftersalesRoute404Tests(unittest.IsolatedAsyncioTestCase):
    """aftersales 路由：资源不存在返回 404（对齐 expenses/mail_record）。"""

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

    async def test_create_with_nonexistent_transaction_returns_404(self):
        """POST /api/aftersales transaction_id 不存在 → 404。"""
        payload = {"transaction_id": 9999, "issue_desc": "问题"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/aftersales", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_update_nonexistent_ticket_returns_404(self):
        """PATCH /api/aftersales/{id} 工单不存在 → 404。"""
        payload = {"status": "resolved"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch("/api/aftersales/9999", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_delete_nonexistent_ticket_returns_404(self):
        """DELETE /api/aftersales/{id} 工单不存在 → 404。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/api/aftersales/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_get_nonexistent_ticket_returns_404(self):
        """GET /api/aftersales/{id} 工单不存在 → 404（回归验证）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/aftersales/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
