import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import ProductTemplate, XianyuAccount, XianyuItem, XianyuSyncLog
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
            id=1,
            cookies="encrypted-old",
            status="online",
            last_error=None,
            updated_at=None,
            unb="old-unb",
            consecutive_failures=0,
            paused_at=None,
            nickname="测试账号",
        )
        fetch_calls = 0

        class FakeDb:
            async def get(self, model, account_id):
                return account

            def add(self, item):
                pass

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


class ItemSyncCircuitBreakerTests(unittest.IsolatedAsyncioTestCase):
    """商品同步熔断：与 order_service 一致——auth_fail/risk 立即暂停；unknown 累计 3 次暂停。"""

    def _make_account(self, **overrides):
        defaults = dict(
            id=1,
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
            nickname="测试账号",
            unb="old-unb",
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def _make_fake_db(self, account):
        class FakeDb:
            async def get(self, model, account_id):
                return account

            def add(self, item):
                pass

            async def flush(self):
                pass

        return FakeDb()

    async def _run_sync(self, account, fetch_side_effect, *, mock_notify=False):
        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False
                self.unb = "old-unb"

        async def fake_fetch_user_id(mtop):
            return "old-unb"

        async def fake_fetch_items(mtop, *, user_id, max_pages):
            if isinstance(fetch_side_effect, Exception):
                raise fetch_side_effect
            return fetch_side_effect

        async def fake_refresh(db, acc):
            return False

        patches = [
            patch.object(item_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(item_service, "MtopClient", FakeMtop),
            patch.object(item_service, "_fetch_user_id", fake_fetch_user_id),
            patch.object(item_service, "fetch_items", fake_fetch_items),
            patch.object(item_service, "refresh_account_cookies_from_cookiecloud", fake_refresh),
        ]
        if mock_notify:
            patches.append(patch.object(item_service, "create_account_paused_notification"))

        for p in patches:
            p.start()
        try:
            return await item_service.sync_items_for_account(self._make_fake_db(account), 1)
        finally:
            for p in patches:
                p.stop()

    async def test_risk_response_pauses_immediately(self):
        account = self._make_account()
        await self._run_sync(
            account,
            item_service.MtopError("RISK", "风控", risk=True),
            mock_notify=True,
        )
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)
        self.assertEqual(account.consecutive_failures, 0)

    async def test_auth_fail_without_refresh_pauses_immediately(self):
        account = self._make_account()
        await self._run_sync(
            account,
            item_service.MtopError("AUTH_FAIL", "session expired", auth_fail=True),
            mock_notify=True,
        )
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)

    async def test_unknown_failure_counts_towards_pause_threshold(self):
        account = self._make_account()
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.consecutive_failures, 1)
        self.assertEqual(account.status, "online")
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.consecutive_failures, 2)
        self.assertEqual(account.status, "online")
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)

    async def test_success_resets_failure_counter(self):
        account = self._make_account(consecutive_failures=2)
        await self._run_sync(account, [])  # 空商品列表=成功
        self.assertEqual(account.consecutive_failures, 0)
        self.assertEqual(account.status, "online")

    async def test_risk_pause_creates_notification(self):
        """风控熔断时应创建 account_paused 通知。"""
        account = self._make_account(nickname="商品账号")

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False
                self.unb = "old-unb"

        async def fake_fetch_items(mtop, *, user_id, max_pages):
            raise item_service.MtopError("RISK", "风控", risk=True)

        with (
            patch.object(item_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(item_service, "MtopClient", FakeMtop),
            patch.object(item_service, "_fetch_user_id", AsyncMock(return_value="old-unb")),
            patch.object(item_service, "fetch_items", fake_fetch_items),
            patch.object(item_service, "refresh_account_cookies_from_cookiecloud", AsyncMock(return_value=False)),
            patch.object(item_service, "create_account_paused_notification") as mock_notify,
        ):
            await item_service.sync_items_for_account(self._make_fake_db(account), 1)

        mock_notify.assert_awaited_once()
        args, kwargs = mock_notify.call_args
        self.assertIn(account.nickname, args)


class ItemSyncLogTests(unittest.IsolatedAsyncioTestCase):
    """商品同步应写 XianyuSyncLog（sync_type='item'）以补审计轨迹。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine, expire_on_commit=False, autoflush=False
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_item_sync_writes_sync_log_with_item_type(self):
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="log-account",
                unb="70001",
                cookies="encrypted",
                status="online",
            )
            db.add(account)
            await db.flush()

            class FakeMtop:
                def __init__(self, cookie_str):
                    self.cookie_str = cookie_str
                    self.cookies_changed = False
                    self.unb = "70001"

            async def fake_fetch_user_id(mtop):
                return "70001"

            async def fake_fetch_items(mtop, *, user_id, max_pages):
                return [
                    {
                        "itemId": "I-1",
                        "title": "测试商品",
                        "priceInfo": {"price": "9.90"},
                        "itemStatus": 0,
                    }
                ]

            with (
                patch.object(item_service, "get_plain_cookies", return_value="old-cookie"),
                patch.object(item_service, "MtopClient", FakeMtop),
                patch.object(item_service, "_fetch_user_id", fake_fetch_user_id),
                patch.object(item_service, "fetch_items", fake_fetch_items),
                patch.object(item_service, "refresh_account_cookies_from_cookiecloud", AsyncMock(return_value=False)),
                patch.object(item_service, "create_account_paused_notification"),
            ):
                result = await item_service.sync_items_for_account(db, account.id)

            self.assertTrue(result["success"])
            await db.flush()
            logs = (await db.execute(select(XianyuSyncLog))).scalars().all()

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].account_id, account.id)
        self.assertEqual(logs[0].status, "success")
        self.assertEqual(logs[0].sync_type, "item")
        self.assertEqual(logs[0].fetched, 1)


if __name__ == "__main__":
    unittest.main()
