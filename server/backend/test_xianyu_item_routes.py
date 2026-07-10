import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import XianyuAccount
from app.services.xianyu.item_service import upsert_item_mirror


class XianyuItemRouteTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_list_account_items_returns_sanitized_account_scoped_rows(self):
        async with self.Session() as db:
            account_a = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            account_b = XianyuAccount(nickname="account-b", cookies="encrypted-b")
            db.add_all([account_a, account_b])
            await db.flush()
            await upsert_item_mirror(
                db,
                account_a.id,
                {
                    "itemId": "ITEM-A",
                    "title": "账号A商品",
                    "priceInfo": {"price": "16.00"},
                    "itemStatus": "出售中",
                    "rawCookieLikeField": "COOKIE_SENTINEL",
                },
            )
            await upsert_item_mirror(
                db,
                account_b.id,
                {"itemId": "ITEM-B", "title": "账号B商品", "price": "99.00"},
            )
            await db.commit()
            account_id = account_a.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/xianyu/accounts/{account_id}/items")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["item_id"], "ITEM-A")
        self.assertEqual(data[0]["title"], "账号A商品")
        self.assertEqual(data[0]["price"], 16.0)
        self.assertNotIn("raw_item", data[0])
        self.assertNotIn("COOKIE_SENTINEL", response.text)

    async def test_import_item_templates_uses_selected_account_scope(self):
        async with self.Session() as db:
            account_a = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            account_b = XianyuAccount(nickname="account-b", cookies="encrypted-b")
            db.add_all([account_a, account_b])
            await db.flush()
            mirror_a = await upsert_item_mirror(
                db,
                account_a.id,
                {"itemId": "ITEM-A", "title": "账号A商品", "price": "16.00"},
            )
            mirror_b = await upsert_item_mirror(
                db,
                account_b.id,
                {"itemId": "ITEM-B", "title": "账号B商品", "price": "99.00"},
            )
            await db.commit()
            account_id = account_a.id
            mirror_ids = [mirror_a.id, mirror_b.id]

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/xianyu/accounts/{account_id}/items/import-templates",
                json={"mirror_ids": mirror_ids},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"created_count": 1, "skipped_count": 1})

    async def test_import_item_templates_allows_zero_warranty_and_rejects_negative_defaults(self):
        async with self.Session() as db:
            account = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            db.add(account)
            await db.flush()
            await db.commit()
            account_id = account.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            negative_cost = await client.post(
                f"/api/xianyu/accounts/{account_id}/items/import-templates",
                json={"mirror_ids": [], "default_cost": -1, "warranty_days": 30},
            )
            zero_warranty = await client.post(
                f"/api/xianyu/accounts/{account_id}/items/import-templates",
                json={"mirror_ids": [], "default_cost": 0, "warranty_days": 0},
            )

        self.assertEqual(negative_cost.status_code, 422)
        self.assertEqual(zero_warranty.status_code, 200)
        self.assertEqual(zero_warranty.json(), {"created_count": 0, "skipped_count": 0})

    async def test_sync_items_route_commits_service_result(self):
        with patch(
            "app.routers.xianyu.sync_items_for_account",
            return_value={"success": True, "fetched": 2, "upserted_count": 2, "error": None},
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post("/api/xianyu/accounts/1/sync-items")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["upserted_count"], 2)


if __name__ == "__main__":
    unittest.main()
