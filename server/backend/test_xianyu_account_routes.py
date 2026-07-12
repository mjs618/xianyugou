import unittest
from datetime import timedelta
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import XianyuAccount
from app.utils.helpers import now_utc


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

    async def test_patch_account_updates_auto_sync_config(self):
        """P3：PATCH 端点支持自动同步开关与间隔配置。"""
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="auto-sync-test",
                unb="20001",
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
                json={"auto_sync_enabled": True, "auto_sync_interval_minutes": 90},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["auto_sync_enabled"])
        self.assertEqual(data["auto_sync_interval_minutes"], 90)
        self.assertNotIn("cookies", data)

    async def test_patch_rejects_interval_below_minimum(self):
        """P3：间隔低于 60 分钟应被 schema 拒绝（422）。"""
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="interval-test",
                unb="30001",
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
                json={"auto_sync_interval_minutes": 30},
            )
        self.assertEqual(response.status_code, 422)

    async def test_recover_returns_404_for_nonexistent_account(self):
        """P3：恢复不存在的账号返回 404。"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/xianyu/accounts/99999/recover")
        self.assertEqual(response.status_code, 404)

    async def test_recover_returns_400_for_non_paused_account(self):
        """P3：恢复非暂停状态的账号返回 400。"""
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="online-account",
                unb="40001",
                cookies="encrypted-cookie",
                status="online",
            )
            db.add(account)
            await db.commit()
            account_id = account.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(f"/api/xianyu/accounts/{account_id}/recover")
        self.assertEqual(response.status_code, 400)
        self.assertIn("未处于暂停状态", response.json()["detail"])

    async def test_manual_order_sync_is_rate_limited_for_sixty_minutes(self):
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="recent-sync",
                unb="50001",
                cookies="encrypted-cookie",
                status="online",
                last_sync_at=now_utc() - timedelta(minutes=30),
            )
            db.add(account)
            await db.commit()
            account_id = account.id

        with patch("app.routers.xianyu.sync_orders_for_account") as sync_orders:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/xianyu/accounts/{account_id}/sync-orders"
                )

        self.assertEqual(response.status_code, 429)
        sync_orders.assert_not_called()

    async def test_paused_account_sync_routes_return_conflict(self):
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="paused-sync",
                unb="60001",
                cookies="encrypted-cookie",
                status="paused",
            )
            db.add(account)
            await db.commit()
            account_id = account.id

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            order_response = await client.post(
                f"/api/xianyu/accounts/{account_id}/sync-orders"
            )
            item_response = await client.post(
                f"/api/xianyu/accounts/{account_id}/sync-items"
            )

        self.assertEqual(order_response.status_code, 409)
        self.assertEqual(item_response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
