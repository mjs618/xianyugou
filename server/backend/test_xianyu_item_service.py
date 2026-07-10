import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import ProductTemplate, XianyuAccount, XianyuItem
from app.services.xianyu.item_service import (
    fetch_items,
    import_item_mirrors_as_templates,
    upsert_item_mirror,
)
from app.services.xianyu import item_service


class XianyuItemServiceTests(unittest.IsolatedAsyncioTestCase):
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

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_fetch_items_parses_top_level_card_list_response(self):
        class FakeMtop:
            async def request(self, api, data, *, version="1.0"):
                return {
                    "cardList": [
                        {
                            "cardType": 1,
                            "cardData": {
                                "id": "ITEM-1",
                                "title": "账号商品",
                                "itemStatus": 0,
                                "priceInfo": {"price": "16.00"},
                                "picInfo": {"picUrl": "https://example.test/item.png"},
                            },
                        }
                    ],
                    "nextPage": False,
                    "totalCount": 1,
                }

        items = await fetch_items(FakeMtop(), user_id="USER-1")

        self.assertEqual(len(items), 1)
        async with self.Session() as db:
            account = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            db.add(account)
            await db.flush()

            mirror = await upsert_item_mirror(db, account.id, items[0])

            self.assertIsNotNone(mirror)
            self.assertEqual(mirror.item_id, "ITEM-1")
            self.assertEqual(mirror.title, "账号商品")
            self.assertEqual(mirror.price, 16.0)
            self.assertEqual(mirror.image_url, "https://example.test/item.png")

    async def test_upsert_item_mirror_is_scoped_by_account(self):
        async with self.Session() as db:
            account_a = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            account_b = XianyuAccount(nickname="account-b", cookies="encrypted-b")
            db.add_all([account_a, account_b])
            await db.flush()

            first = await upsert_item_mirror(
                db,
                account_a.id,
                {
                    "itemId": "ITEM-1",
                    "title": "账号A商品",
                    "priceInfo": {"price": "12.50"},
                    "itemStatus": "出售中",
                    "picInfo": {"picUrl": "https://example.test/a.png"},
                    "rawCookieLikeField": "COOKIE_SENTINEL",
                },
            )
            second = await upsert_item_mirror(
                db,
                account_b.id,
                {
                    "itemId": "ITEM-1",
                    "title": "账号B商品",
                    "priceInfo": {"price": "99.00"},
                    "itemStatus": "已售出",
                },
            )
            updated = await upsert_item_mirror(
                db,
                account_a.id,
                {
                    "itemId": "ITEM-1",
                    "title": "账号A商品-改名",
                    "priceInfo": {"price": "13.00"},
                },
            )

            self.assertEqual(first.id, updated.id)
            self.assertNotEqual(first.id, second.id)

            rows = (
                await db.execute(select(XianyuItem).order_by(XianyuItem.account_id.asc()))
            ).scalars().all()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].account_id, account_a.id)
            self.assertEqual(rows[0].item_id, "ITEM-1")
            self.assertEqual(rows[0].title, "账号A商品-改名")
            self.assertEqual(rows[0].price, 13.0)
            self.assertEqual(rows[1].account_id, account_b.id)
            self.assertEqual(rows[1].title, "账号B商品")

    async def test_import_item_mirrors_as_templates_only_imports_selected_account_items(self):
        async with self.Session() as db:
            account_a = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            account_b = XianyuAccount(nickname="account-b", cookies="encrypted-b")
            db.add_all([account_a, account_b])
            await db.flush()

            mirror_a = await upsert_item_mirror(
                db,
                account_a.id,
                {
                    "itemId": "A-1",
                    "title": "账号A商品",
                    "price": "68.00",
                    "picInfo": {"picUrl": "https://example.test/a.png"},
                },
            )
            mirror_b = await upsert_item_mirror(
                db,
                account_b.id,
                {"itemId": "B-1", "title": "账号B商品", "price": "88.00"},
            )

            result = await import_item_mirrors_as_templates(
                db,
                account_a.id,
                mirror_ids=[mirror_a.id, mirror_b.id],
                default_cost=0,
                warranty_days=30,
            )

            self.assertEqual(result, {"created_count": 1, "skipped_count": 1})
            templates = (await db.execute(select(ProductTemplate))).scalars().all()
            self.assertEqual(len(templates), 1)
            self.assertEqual(templates[0].name, "账号A商品")
            self.assertEqual(templates[0].default_sale_price, 68.0)
            self.assertEqual(templates[0].source_xianyu_account_id, account_a.id)
            self.assertEqual(templates[0].source_xianyu_item_id, "A-1")
            self.assertEqual(templates[0].image_url, "https://example.test/a.png")

            await db.refresh(mirror_a)
            await db.refresh(mirror_b)
            self.assertEqual(mirror_a.projected_template_id, templates[0].id)
            self.assertIsNone(mirror_b.projected_template_id)

    async def test_import_item_mirrors_reuses_existing_template_for_same_account_item(self):
        async with self.Session() as db:
            account = XianyuAccount(nickname="account-a", cookies="encrypted-a")
            db.add(account)
            await db.flush()
            mirror = await upsert_item_mirror(
                db,
                account.id,
                {"itemId": "A-1", "title": "账号A商品", "price": "68.00"},
            )
            existing_template = ProductTemplate(
                name="账号A商品旧模板",
                default_cost=0,
                default_sale_price=66,
                category="闲鱼导入",
                warranty_days=30,
                is_active=True,
                source_xianyu_account_id=account.id,
                source_xianyu_item_id="A-1",
            )
            db.add(existing_template)
            await db.flush()

            result = await import_item_mirrors_as_templates(
                db,
                account.id,
                mirror_ids=[mirror.id],
                default_cost=0,
                warranty_days=30,
            )

            self.assertEqual(result, {"created_count": 0, "skipped_count": 1})
            templates = (await db.execute(select(ProductTemplate))).scalars().all()
            self.assertEqual(len(templates), 1)
            await db.refresh(mirror)
            self.assertEqual(mirror.projected_template_id, existing_template.id)

    async def test_sync_items_refreshes_cookiecloud_once_after_auth_fail(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            updated_at=None,
            unb="old-unb",
        )
        fetch_calls = 0

        class FakeDb:
            async def get(self, model, account_id):
                return account

            async def flush(self):
                pass

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False
                self.unb = "old-unb"

        async def fake_fetch_user_id(mtop):
            return "old-unb"

        async def fake_fetch_items(mtop, *, user_id, max_pages):
            nonlocal fetch_calls
            fetch_calls += 1
            if fetch_calls == 1:
                raise item_service.MtopError(
                    "AUTH_FAIL",
                    "session expired",
                    auth_fail=True,
                )
            return []

        async def fake_refresh(db, account):
            account.cookies = "encrypted-new"
            return True

        with (
            patch.object(item_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(item_service, "MtopClient", FakeMtop),
            patch.object(item_service, "_fetch_user_id", fake_fetch_user_id),
            patch.object(item_service, "fetch_items", fake_fetch_items),
            patch.object(item_service, "refresh_account_cookies_from_cookiecloud", fake_refresh),
        ):
            result = await item_service.sync_items_for_account(FakeDb(), 1)

        self.assertEqual(fetch_calls, 2)
        self.assertTrue(result["success"])
        self.assertIsNone(account.last_error)


if __name__ == "__main__":
    unittest.main()
