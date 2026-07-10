import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


class ProductTemplateRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_template_allows_zero_warranty(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/product-templates",
                json={"name": "no warranty", "default_cost": 10, "warranty_days": 0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["warranty_days"], 0)

    async def test_create_template_rejects_negative_warranty(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/product-templates",
                json={"name": "bad warranty", "default_cost": 10, "warranty_days": -1},
            )

        self.assertEqual(response.status_code, 422)

    async def test_update_template_allows_zero_warranty(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/product-templates",
                json={"name": "editable", "default_cost": 10, "warranty_days": 30},
            )
            response = await client.patch(
                f"/api/product-templates/{created.json()['id']}",
                json={"warranty_days": 0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["warranty_days"], 0)

    async def test_update_template_rejects_negative_warranty(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/product-templates",
                json={"name": "editable", "default_cost": 10, "warranty_days": 30},
            )
            response = await client.patch(
                f"/api/product-templates/{created.json()['id']}",
                json={"warranty_days": -1},
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
