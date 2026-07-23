import asyncio
import unittest
import warnings
from contextlib import suppress
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.xianyu import item_service, order_parser, order_service


def make_order(
    order_id: int,
    *,
    status: str = "交易成功",
    price: str = "88.00",
) -> dict:
    return {
        "buyerInfoVO": {"userNick": "测试买家"},
        "commonData": {
            "orderId": order_id,
            "orderStatus": status,
            "finishTime": "2026-07-01 12:34:56",
        },
        "itemVO": {"title": "测试商品"},
        "priceVO": {"confirmFee": price},
    }


class OrderParsingTests(unittest.TestCase):
    def test_parse_orders_supports_current_module_items_shape(self):
        orders = [make_order(1001)]

        self.assertEqual(
            order_parser.parse_orders({"module": {"items": orders}}),
            orders,
        )

    def test_extractors_support_current_nested_fields(self):
        order = make_order(1001)

        self.assertEqual(order_parser.extract_order_no(order), "1001")
        self.assertEqual(order_parser.extract_price(order), 88.0)
        self.assertEqual(order_parser.extract_buyer_nick(order), "测试买家")
        self.assertEqual(order_parser.extract_product_name(order), "测试商品")
        self.assertEqual(
            order_parser.parse_trade_time(order),
            datetime(2026, 7, 1, 12, 34, 56),
        )

    def test_platform_order_status_maps_to_projection_status(self):
        self.assertEqual(
            order_parser.project_transaction_status(make_order(1001)),
            "completed",
        )
        self.assertEqual(
            order_parser.project_transaction_status(make_order(1002, status="待发货")),
            "pending",
        )
        self.assertEqual(
            order_parser.project_transaction_status(make_order(1003, status="退款处理中")),
            "aftersales",
        )
        self.assertIsNone(
            order_parser.project_transaction_status(
                make_order(1004, status="交易关闭"),
            )
        )


class FetchOrdersTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_orders_follows_current_next_page_flag(self):
        class FakeMtop:
            def __init__(self):
                self.pages = []

            async def request(self, api, data, *, version):
                page = data["pageNumber"]
                self.pages.append(page)
                return {
                    "module": {
                        "items": [make_order(page)],
                        "nextPage": page == 1,
                    }
                }

        mtop = FakeMtop()

        orders = await order_service.fetch_orders(mtop)

        self.assertEqual([order["commonData"]["orderId"] for order in orders], [1, 2])
        self.assertEqual(mtop.pages, [1, 2])


class SyncOrdersTests(unittest.IsolatedAsyncioTestCase):
    async def test_paused_account_is_rejected_before_mtop_client_creation(self):
        account = SimpleNamespace(status="paused")

        class FakeDb:
            async def get(self, model, account_id):
                return account

        with patch.object(order_service, "MtopClient") as mtop_client:
            with self.assertRaisesRegex(ValueError, "暂停"):
                await order_service.sync_orders_for_account(FakeDb(), 1)

        mtop_client.assert_not_called()

    async def test_paused_account_item_sync_is_rejected_before_mtop_client_creation(self):
        account = SimpleNamespace(status="paused")

        class FakeDb:
            async def get(self, model, account_id):
                return account

        with patch.object(item_service, "MtopClient") as mtop_client:
            with self.assertRaisesRegex(ValueError, "暂停"):
                await item_service.sync_items_for_account(FakeDb(), 1)

        mtop_client.assert_not_called()

    async def test_sync_persists_refreshed_cookies(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
        )

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

        async def fake_fetch_orders(mtop, *, max_pages):
            mtop.cookie_str = "unb=1; _m_h5_tk=newtoken_2000; _m_h5_tk_enc=newenc"
            mtop.cookies_changed = True
            return []

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(
                order_service,
                "encrypt_field",
                side_effect=lambda value: f"encrypted:{value}",
                create=True,
            ),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await order_service.sync_orders_for_account(FakeDb(), 1)

        self.assertEqual(
            account.cookies,
            "encrypted:unb=1; _m_h5_tk=newtoken_2000; _m_h5_tk_enc=newenc",
        )

    async def test_sync_rejects_concurrent_run_for_same_account(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
        )
        fetch_started = asyncio.Event()
        release_fetch = asyncio.Event()
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

        async def fake_fetch_orders(mtop, *, max_pages):
            nonlocal fetch_calls
            fetch_calls += 1
            fetch_started.set()
            await release_fetch.wait()
            return []

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
        ):
            first = asyncio.create_task(order_service.sync_orders_for_account(FakeDb(), 1))
            await fetch_started.wait()

            second = asyncio.create_task(order_service.sync_orders_for_account(FakeDb(), 1))
            try:
                with self.assertRaises(order_service.SyncAlreadyRunningError):
                    await asyncio.wait_for(second, timeout=0.05)
            except asyncio.TimeoutError:
                second.cancel()
                with suppress(asyncio.CancelledError):
                    await second
                self.fail("concurrent sync should fail before starting another fetch")
            finally:
                release_fetch.set()
                await first

        self.assertEqual(fetch_calls, 1)

    async def test_sync_refreshes_cookiecloud_once_after_auth_fail(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
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

        async def fake_fetch_orders(mtop, *, max_pages):
            nonlocal fetch_calls
            fetch_calls += 1
            if fetch_calls == 1:
                raise order_service.MtopError(
                    "AUTH_FAIL",
                    "session expired",
                    auth_fail=True,
                )
            return []

        async def fake_refresh(db, account):
            account.cookies = "encrypted-new"
            return True

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "refresh_account_cookies_from_cookiecloud", fake_refresh),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = await order_service.sync_orders_for_account(FakeDb(), 1)

        self.assertEqual(fetch_calls, 2)
        self.assertTrue(result["success"])
        self.assertIsNone(account.last_error)

    async def test_sync_auth_fail_preserves_cookiecloud_failure_guidance(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
            nickname="测试账号",
        )

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

        async def fake_fetch_orders(mtop, *, max_pages):
            raise order_service.MtopError(
                "AUTH_FAIL",
                "session expired",
                auth_fail=True,
            )

        async def fake_refresh(db, account):
            account.last_error = "Cookie 已过期，CookieCloud 自动续 Cookie 未启用：缺少 COOKIE_CLOUD_UUID。下一步：补齐配置或手动更新账号 Cookie。"
            account.status = "invalid"
            return False

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "refresh_account_cookies_from_cookiecloud", fake_refresh),
            patch.object(order_service, "create_account_paused_notification"),
        ):
            result = await order_service.sync_orders_for_account(FakeDb(), 1)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], account.last_error)
        self.assertIn("自动续 Cookie 未启用", result["error"])
        self.assertIn("下一步", result["error"])
        # P3：登录态失效应立即熔断暂停（而非旧 invalid 状态）
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)


class CircuitBreakerTests(unittest.IsolatedAsyncioTestCase):
    """P3 安全调度熔断：auth_fail/risk 立即暂停；未知失败累计 3 次暂停。"""

    def _make_account(self, **overrides):
        defaults = dict(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
            nickname="测试账号",
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

        async def fake_fetch_orders(mtop, *, max_pages):
            if isinstance(fetch_side_effect, Exception):
                raise fetch_side_effect
            return fetch_side_effect

        patches = [
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
        ]
        if mock_notify:
            patches.append(patch.object(order_service, "create_account_paused_notification"))

        for p in patches:
            p.start()
        try:
            return await order_service.sync_orders_for_account(self._make_fake_db(account), 1)
        finally:
            for p in patches:
                p.stop()

    async def test_risk_response_pauses_immediately(self):
        account = self._make_account()
        await self._run_sync(
            account,
            order_service.MtopError("RISK", "风控", risk=True),
            mock_notify=True,
        )
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)
        self.assertEqual(account.consecutive_failures, 0)

    async def test_unknown_failure_counts_towards_pause_threshold(self):
        account = self._make_account()
        # 第 1 次未知失败：计数 1，未暂停
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.consecutive_failures, 1)
        self.assertEqual(account.status, "online")
        # 第 2 次：计数 2，未暂停
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.consecutive_failures, 2)
        self.assertEqual(account.status, "online")
        # 第 3 次：达到阈值，熔断暂停
        await self._run_sync(account, RuntimeError("网络超时"), mock_notify=True)
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)

    async def test_success_resets_failure_counter(self):
        account = self._make_account(consecutive_failures=2)
        await self._run_sync(account, [])  # 空订单列表=成功
        self.assertEqual(account.consecutive_failures, 0)
        self.assertEqual(account.status, "online")
        self.assertIsNone(account.paused_at)

    async def test_risk_pause_creates_notification(self):
        """P3 告警：风控熔断时应创建 account_paused 通知。"""
        account = self._make_account(nickname="测试账号")

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False

        async def fake_fetch_orders(mtop, *, max_pages):
            raise order_service.MtopError("RISK", "风控", risk=True)

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "create_account_paused_notification") as mock_notify,
        ):
            await order_service.sync_orders_for_account(self._make_fake_db(account), 1)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        self.assertEqual(call_args.args[1], 1)  # account_id
        self.assertEqual(call_args.args[2], "测试账号")  # nickname
        self.assertIn("风控", call_args.args[3])  # reason

    async def test_threshold_pause_creates_notification(self):
        """P3 告警：连续失败熔断时应创建 account_paused 通知。"""
        account = self._make_account(consecutive_failures=2, nickname="累计失败号")

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False

        async def fake_fetch_orders(mtop, *, max_pages):
            raise RuntimeError("网络超时")

        with (
            patch.object(order_service, "get_plain_cookies", return_value="old-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "create_account_paused_notification") as mock_notify,
        ):
            await order_service.sync_orders_for_account(self._make_fake_db(account), 1)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        self.assertEqual(call_args.args[1], 1)  # account_id
        self.assertEqual(call_args.args[2], "累计失败号")  # nickname
        self.assertIn("连续失败", call_args.args[3])  # reason

    async def test_cookiecloud_retry_unknown_error_does_not_pause_immediately(self):
        account = self._make_account()
        fetch_calls = 0

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False

        async def fake_fetch_orders(mtop, *, max_pages):
            nonlocal fetch_calls
            fetch_calls += 1
            if fetch_calls == 1:
                raise order_service.MtopError("AUTH_FAIL", "expired", auth_fail=True)
            raise order_service.MtopError("BIZ_FAIL", "temporary business failure")

        async def fake_refresh(db, target):
            target.cookies = "encrypted-new"
            return True

        with (
            patch.object(order_service, "get_plain_cookies", return_value="cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "refresh_account_cookies_from_cookiecloud", fake_refresh),
        ):
            result = await order_service.sync_orders_for_account(
                self._make_fake_db(account), 1
            )

        self.assertFalse(result["success"])
        self.assertEqual(account.status, "online")
        self.assertEqual(account.consecutive_failures, 1)

    def test_apply_projection_returns_true_on_status_change(self):
        """_apply_order_projection_to_transaction：状态变更返回 True，未变更返回 False。"""
        from app.utils.helpers import now_utc
        tx = SimpleNamespace(
            status="completed", shipped_at=None, warranty_end=None,
            warranty_days=30, trade_at=now_utc(), version=0, updated_at=None,
        )
        order = make_order(1001, status="退款成功")
        # completed → closed：状态变更，应返回 True
        self.assertTrue(order_service._apply_order_projection_to_transaction(tx, order, "closed"))
        self.assertEqual(tx.status, "closed")
        self.assertGreaterEqual(tx.version, 1)
        # 再次投影 closed：状态未变更，应返回 False
        self.assertFalse(order_service._apply_order_projection_to_transaction(tx, order, "closed"))

    async def test_status_change_triggers_customer_stats_recalc(self):
        """P1: 订单状态变更时触发受影响客户的统计重算。"""
        account = self._make_account()
        existing_tx = SimpleNamespace(
            id=100, customer_id=200, status="completed",
            shipped_at=None, warranty_end=None, warranty_days=30,
            trade_at=datetime(2026, 7, 1), version=0, updated_at=None,
            cost_price=0.0, product_template_id=None, sale_price=10.0,
            xianyu_order_no="1001",
        )

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

        async def fake_fetch_orders(mtop, *, max_pages):
            return [make_order(1001, status="退款成功")]

        fake_mirror = SimpleNamespace(order_no="1001", projected_transaction_id=None)

        # P1-4 批量化重构后：直接 mock _prefetch_sync_lookups 返回三元组
        # 替代原 FakeDb.execute + scalar_one_or_none 的逐单查询 mock
        async def fake_prefetch(db, account_id, orders):
            return ({"1001": existing_tx}, {}, {})

        with (
            patch.object(order_service, "get_plain_cookies", return_value="cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "upsert_order_mirror", return_value=fake_mirror),
            patch.object(order_service, "project_transaction_status", return_value="closed"),
            patch.object(order_service, "_prefetch_sync_lookups", side_effect=fake_prefetch),
            patch.object(order_service, "recalc_customer_stats") as mock_recalc,
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await order_service.sync_orders_for_account(FakeDb(), 1)

        # 状态 completed → closed，应触发 customer_id=200 的统计重算
        mock_recalc.assert_awaited_once()
        self.assertEqual(mock_recalc.call_args.args[1], 200)

    async def test_no_recalc_when_status_unchanged(self):
        """P1: 订单状态未变更时不触发客户统计重算。"""
        account = self._make_account()
        existing_tx = SimpleNamespace(
            id=100, customer_id=200, status="completed",
            shipped_at=None, warranty_end=None, warranty_days=30,
            trade_at=datetime(2026, 7, 1), version=0, updated_at=None,
            cost_price=0.0, product_template_id=None, sale_price=10.0,
            xianyu_order_no="1001",
        )

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

        async def fake_fetch_orders(mtop, *, max_pages):
            return [make_order(1001)]

        fake_mirror = SimpleNamespace(order_no="1001", projected_transaction_id=None)

        async def fake_prefetch(db, account_id, orders):
            return ({"1001": existing_tx}, {}, {})

        with (
            patch.object(order_service, "get_plain_cookies", return_value="cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "upsert_order_mirror", return_value=fake_mirror),
            # 投影状态与现有交易相同 → 不变更
            patch.object(order_service, "project_transaction_status", return_value="completed"),
            patch.object(order_service, "_prefetch_sync_lookups", side_effect=fake_prefetch),
            patch.object(order_service, "recalc_customer_stats") as mock_recalc,
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await order_service.sync_orders_for_account(FakeDb(), 1)

        # 状态未变更，不应调用 recalc_customer_stats
        mock_recalc.assert_not_awaited()

    async def test_notification_failure_does_not_block_pause(self):
        """P1: 通知创建失败时不应阻断熔断状态写入。"""
        account = self._make_account()

        async def boom(*args, **kwargs):
            raise RuntimeError("DB 写入通知失败")

        with (
            patch.object(order_service, "get_plain_cookies", return_value="cookie"),
            patch.object(order_service, "MtopClient", lambda *a, **kw: SimpleNamespace(cookie_str="", cookies_changed=False)),
            patch.object(order_service, "fetch_orders", side_effect=order_service.MtopError("RISK", "风控", risk=True)),
            patch.object(order_service, "create_account_paused_notification", side_effect=boom),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await order_service.sync_orders_for_account(self._make_fake_db(account), 1)

        # 即使通知创建失败，账号仍应被熔断
        self.assertEqual(account.status, "paused")
        self.assertIsNotNone(account.paused_at)


if __name__ == "__main__":
    unittest.main()
