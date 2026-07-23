"""customer-tag 路由 404 语义测试。

验证 project_memory 硬约束「资源不存在返回 404」对齐 expenses/mail_record/aftersales/warranty/customers：

1. POST /api/customer-tags/set-customer/{id} 客户不存在 → 404
2. DELETE /api/customer-tags/{id} 标签不存在 → 404（原静默返回 200，现对齐 404）
"""
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class CustomerTagRoute404Tests(unittest.IsolatedAsyncioTestCase):
    """customer-tag 路由：资源不存在返回 404（对齐 expenses/mail_record/aftersales/warranty/customers）。"""

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

    async def test_set_customer_tags_nonexistent_customer_returns_404(self):
        """POST /api/customer-tags/set-customer/{id} 客户不存在 → 404（不返回 400）。"""
        payload = {"tags": ["VIP"]}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/customer-tags/set-customer/9999", json=payload
            )
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_delete_nonexistent_tag_returns_404(self):
        """DELETE /api/customer-tags/{id} 标签不存在 → 404（原静默返回 200，现对齐 404）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/api/customer-tags/9999")
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
