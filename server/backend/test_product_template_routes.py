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

    async def test_delete_nonexistent_template_returns_404(self):
        """DELETE 不存在的 id 应返回 404（与 update/toggle 行为一致，对齐 expenses/mail_record/aftersales）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/product-templates/9999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("不存在", response.json()["detail"])

    async def test_create_template_rejects_negative_default_cost(self):
        """POST default_cost=-1 应返回 422（成本不能为负数，与 warranty_days ge=0 一致）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/product-templates",
                json={"name": "bad cost", "default_cost": -1, "warranty_days": 30},
            )

        self.assertEqual(response.status_code, 422)

    async def test_create_template_rejects_negative_default_sale_price(self):
        """POST default_sale_price=-1 应返回 422（售价不能为负数）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/product-templates",
                json={
                    "name": "bad price",
                    "default_cost": 10,
                    "default_sale_price": -1,
                    "warranty_days": 30,
                },
            )

        self.assertEqual(response.status_code, 422)

    async def test_create_template_allows_zero_default_cost(self):
        """POST default_cost=0 应允许（0 元成本是合法值，如赠品）。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/product-templates",
                json={"name": "free", "default_cost": 0, "warranty_days": 30},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["default_cost"], 0)

    async def test_update_template_rejects_negative_default_cost(self):
        """PATCH default_cost=-1 应返回 422（更新时也校验负数）。"""
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
                json={"default_cost": -1},
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
