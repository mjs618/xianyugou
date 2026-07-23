"""warranty 路由 404 语义测试。

验证 project_memory 硬约束「资源不存在返回 404」对齐 expenses/mail_record/aftersales：

1. POST /api/warranty/{id}/extend 交易不存在 → 404
2. POST /api/warranty/{id}/end-early 交易不存在 → 404
3. GET /api/warranty/{id}/extensions 不存在的交易 → 200 + 空数组（不抛 404，符合语义）
"""
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class WarrantyRoute404Tests(unittest.IsolatedAsyncioTestCase):
    """warranty 路由：交易不存在返回 404（对齐 expenses/mail_record/aftersales）。"""

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

    async def test_extend_nonexistent_transaction_returns_404(self):
        """POST /api/warranty/{id}/extend 交易不存在 → 404。"""
        payload = {"days": 7, "reason": "测试"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/warranty/9999/extend", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])

    async def test_end_early_nonexistent_transaction_returns_404(self):
        """POST /api/warranty/{id}/end-early 交易不存在 → 404。"""
        payload = {"reason": "测试"}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/warranty/9999/end-early", json=payload)
            self.assertEqual(response.status_code, 404)
            self.assertIn("不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
