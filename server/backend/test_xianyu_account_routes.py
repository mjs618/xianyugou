import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import XianyuAccount


class XianyuAccountRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_update_account_renames_existing_account_without_exposing_cookie(self):
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="old-name",
                unb="10001",
                cookies="encrypted-cookie",
            )
            db.add(account)
            await db.commit()
            account_id = account.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                f"/api/xianyu/accounts/{account_id}",
                json={"nickname": "new-name"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["nickname"], "new-name")
        self.assertEqual(data["unb"], "10001")
        self.assertNotIn("cookies", data)
        self.assertNotIn("encrypted-cookie", response.text)

    async def test_cookiecloud_status_does_not_expose_secret_values(self):
        from app.config import settings

        old_values = (
            settings.cookie_cloud_host,
            settings.cookie_cloud_uuid,
            settings.cookie_cloud_password,
        )
        settings.cookie_cloud_host = "http://secret-host.local"
        settings.cookie_cloud_uuid = "secret-uuid"
        settings.cookie_cloud_password = "secret-password"
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/xianyu/cookiecloud/status")
        finally:
            (
                settings.cookie_cloud_host,
                settings.cookie_cloud_uuid,
                settings.cookie_cloud_password,
            ) = old_values

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["enabled"])
        self.assertNotIn("secret-host.local", response.text)
        self.assertNotIn("secret-uuid", response.text)
        self.assertNotIn("secret-password", response.text)


if __name__ == "__main__":
    unittest.main()
