import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class SettingsRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def test_update_settings_allows_zero_warranty_days(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put("/api/settings", json={"warranty_days": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["warranty_days"], 0)

    async def test_update_settings_rejects_negative_warranty_days(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put("/api/settings", json={"warranty_days": -1})

        self.assertEqual(response.status_code, 400)

    async def test_update_settings_allows_zero_recall_days(self):
        """recall_days=0 允许（表示不回访），与 warranty_days=0 行为一致。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put("/api/settings", json={"recall_days": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recall_days"], 0)

    async def test_update_settings_rejects_negative_recall_days(self):
        """recall_days=-1 拒绝（回访天数不能为负数），与 warranty_days 行为一致。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.put("/api/settings", json={"recall_days": -1})

        self.assertEqual(response.status_code, 400)
        self.assertIn("回访天数", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
