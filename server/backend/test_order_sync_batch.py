"""P1-4 修复验证：订单同步批量化。

覆盖：
1. _prefetch_sync_lookups 返回 (existing_tx_map, template_map, customer_map) 三元组
2. 空订单列表时返回三个空 dict
3. _ensure_customer 命中 customer_map 时不查询 DB
4. _ensure_customer 未命中时走 DB 并增量写回 customer_map
5. _lookup_customer 按小写键查找
6. 主循环使用 map 替代逐单 DB 查询（N 单 ≤ 6 次 SELECT，含 prefetch 的 3 次）
"""
import asyncio
import unittest
import warnings
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.xianyu import order_service


def make_order(
    order_id: int,
    *,
    item_id: str = "item-1",
    buyer_nick: str = "测试买家",
    status: str = "交易成功",
    price: str = "88.00",
) -> dict:
    return {
        "buyerInfoVO": {"userNick": buyer_nick},
        "commonData": {
            "orderId": order_id,
            "orderStatus": status,
            "itemId": item_id,
            "finishTime": "2026-07-01 12:34:56",
        },
        "itemVO": {"title": f"测试商品-{item_id}"},
        "priceVO": {"confirmFee": price},
    }


class FakeResult:
    """模拟 SQLAlchemy Result 的链式调用：scalars().all() / scalar_one_or_none()。

    AsyncMock 的属性方法会自动变 coroutine，不能用来模拟同步的 Result 对象。
    用普通类 + MagicMock 更可靠。
    """

    def __init__(self, items: list | None = None, single=None):
        self._items = items or []
        self._single = single

    def scalars(self):
        return self

    def all(self):
        return list(self._items)

    def scalar_one_or_none(self):
        return self._single


def make_fake_db(execute_results=None):
    """构造 FakeDb，execute 按 execute_results 顺序返回 FakeResult。

    execute_results 为 None 时所有 execute 返回空结果（用于 prefetch 测试）。
    """
    class FakeDb:
        def __init__(self):
            self._results = list(execute_results) if execute_results else None
            self.execute_calls = 0

        async def get(self, model, account_id):
            return None  # 测试中不关心

        def add(self, item):
            pass

        async def execute(self, stmt):
            self.execute_calls += 1
            if self._results is not None:
                return self._results.pop(0)
            return FakeResult()

        async def flush(self):
            pass

    return FakeDb()


class PrefetchSyncLookupsTests(unittest.IsolatedAsyncioTestCase):
    """_prefetch_sync_lookups 批量预取行为验证。"""

    async def test_empty_orders_returns_empty_dicts(self):
        """空订单列表返回三个空 dict，不调用 DB。"""
        db = make_fake_db()

        result = await order_service._prefetch_sync_lookups(db, 1, [])

        self.assertEqual(result, ({}, {}, {}))
        self.assertEqual(db.execute_calls, 0)

    async def test_returns_three_tuple_of_dicts(self):
        """有订单时返回三个 dict（即使 DB 返回空也是 dict 而非 None）。"""
        # 模拟 db.execute 返回空列表（三次：tx / template / customer）
        db = make_fake_db(execute_results=[
            FakeResult(items=[]),
            FakeResult(items=[]),
            FakeResult(items=[]),
        ])

        orders = [make_order(1001), make_order(1002, item_id="item-2")]

        existing_tx_map, template_map, customer_map = (
            await order_service._prefetch_sync_lookups(db, 1, orders)
        )

        self.assertEqual(existing_tx_map, {})
        self.assertEqual(template_map, {})
        self.assertEqual(customer_map, {})
        # 3 次 SELECT：existing_tx / template / customer
        self.assertEqual(db.execute_calls, 3)

    async def test_populates_existing_tx_map_by_order_no(self):
        """existing_tx_map 按 xianyu_order_no 索引。"""
        tx = SimpleNamespace(xianyu_order_no="1001", id=42, status="completed")
        db = make_fake_db(execute_results=[
            FakeResult(items=[tx]),   # existing_tx
            FakeResult(items=[]),     # template
            FakeResult(items=[]),     # customer
        ])

        orders = [make_order(1001), make_order(1002)]
        existing_tx_map, _, _ = await order_service._prefetch_sync_lookups(db, 1, orders)

        self.assertEqual(existing_tx_map, {"1001": tx})

    async def test_template_map_keeps_latest_id_for_duplicate_item(self):
        """同一 item_id 多条模板时取 id 最大（最新）的一条。"""
        # 两条模板对应同一 item_id，id 大的应保留
        tpl_old = SimpleNamespace(id=1, source_xianyu_item_id="item-1", default_cost=10.0)
        tpl_new = SimpleNamespace(id=5, source_xianyu_item_id="item-1", default_cost=20.0)
        db = make_fake_db(execute_results=[
            FakeResult(items=[]),                   # existing_tx
            FakeResult(items=[tpl_old, tpl_new]),   # template（两条）
            FakeResult(items=[]),                   # customer
        ])

        orders = [make_order(1001, item_id="item-1")]
        _, template_map, _ = await order_service._prefetch_sync_lookups(db, 1, orders)

        self.assertEqual(template_map, {"item-1": tpl_new})

    async def test_customer_map_uses_lowercase_keys(self):
        """customer_map 按 xianyu_nickname 小写键存储。"""
        customer = SimpleNamespace(id=7, xianyu_nickname="TestBuyer")
        db = make_fake_db(execute_results=[
            FakeResult(items=[]),                    # existing_tx
            FakeResult(items=[]),                    # template
            FakeResult(items=[customer]),             # customer
        ])

        orders = [make_order(1001, buyer_nick="TestBuyer")]
        _, _, customer_map = await order_service._prefetch_sync_lookups(db, 1, orders)

        self.assertEqual(customer_map, {"testbuyer": customer})


class LookupCustomerTests(unittest.TestCase):
    """_lookup_customer 小写键查找行为。"""

    def test_returns_none_for_empty_map(self):
        self.assertIsNone(order_service._lookup_customer({}, "anyone"))
        self.assertIsNone(order_service._lookup_customer(None, "anyone"))

    def test_returns_none_for_missing_key(self):
        customer_map = {"alice": SimpleNamespace(id=1)}
        self.assertIsNone(order_service._lookup_customer(customer_map, "bob"))

    def test_finds_case_insensitively(self):
        customer = SimpleNamespace(id=1)
        customer_map = {"alice": customer}
        # 大小写不同的输入都应命中
        self.assertIs(order_service._lookup_customer(customer_map, "ALICE"), customer)
        self.assertIs(order_service._lookup_customer(customer_map, "Alice"), customer)
        self.assertIs(order_service._lookup_customer(customer_map, "alice"), customer)

    def test_strips_whitespace(self):
        customer = SimpleNamespace(id=1)
        customer_map = {"alice": customer}
        self.assertIs(order_service._lookup_customer(customer_map, "  alice  "), customer)


class EnsureCustomerCacheTests(unittest.IsolatedAsyncioTestCase):
    """_ensure_customer 在 customer_map 模式下的缓存行为。"""

    async def test_hits_cache_without_db_call(self):
        """customer_map 命中时不调用 find_by_nickname / create_customer。"""
        cached = SimpleNamespace(id=1, xianyu_nickname="cachedbuyer")
        # 键需与 nickname 的 strip().lower() 一致
        customer_map = {"cachedbuyer": cached}
        db = make_fake_db()

        # 关键：find_by_nickname 和 create_customer 都不应被调用
        with (
            patch.object(order_service, "find_by_nickname", side_effect=AssertionError("不应调用 find_by_nickname")),
            patch.object(order_service, "create_customer", side_effect=AssertionError("不应调用 create_customer")),
        ):
            result = await order_service._ensure_customer(db, "CachedBuyer", customer_map)

        self.assertIs(result, cached)
        self.assertEqual(db.execute_calls, 0)

    async def test_misses_cache_falls_back_to_db_and_writes_back(self):
        """customer_map 未命中时走 find_by_nickname，命中后写回 map。"""
        from_db = SimpleNamespace(id=2, xianyu_nickname="dbbuyer")
        customer_map: dict = {}
        db = make_fake_db()

        with patch.object(order_service, "find_by_nickname", return_value=from_db):
            result = await order_service._ensure_customer(db, "DB-Buyer", customer_map)

        self.assertIs(result, from_db)
        # 应已写回 map（小写键）
        self.assertEqual(customer_map, {"db-buyer": from_db})

    async def test_creates_new_customer_when_not_found_and_writes_back(self):
        """customer_map 未命中且 DB 未找到时调用 create_customer，并写回 map。"""
        created = SimpleNamespace(id=3, xianyu_nickname="newbuyer")
        customer_map: dict = {}
        db = make_fake_db()

        with (
            patch.object(order_service, "find_by_nickname", return_value=None),
            patch.object(order_service, "create_customer", return_value=created),
        ):
            result = await order_service._ensure_customer(db, "New-Buyer", customer_map)

        self.assertIs(result, created)
        self.assertEqual(customer_map, {"new-buyer": created})

    async def test_no_map_uses_original_behavior(self):
        """不传 customer_map 时走原逻辑（find_by_nickname + create_customer）。"""
        from_db = SimpleNamespace(id=4, xianyu_nickname="legacybuyer")
        db = make_fake_db()

        with patch.object(order_service, "find_by_nickname", return_value=from_db):
            result = await order_service._ensure_customer(db, "Legacy-Buyer")

        self.assertIs(result, from_db)


class SyncBatchQueryCountTests(unittest.IsolatedAsyncioTestCase):
    """主循环使用 map 替代逐单 DB 查询的端到端验证。

    场景：200 单全为新建（existing_tx_map 空、template_map 空、customer_map 空），
    应仅触发 3 次 prefetch SELECT，循环内不再有逐单 SELECT。
    """

    def _make_account(self):
        return SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
            consecutive_failures=0,
            paused_at=None,
            nickname="测试账号",
        )

    async def test_200_orders_trigger_at_most_3_select_in_prefetch(self):
        """200 单场景下 prefetch SELECT 次数 ≤ 3（existing_tx / template / customer 各一次）。"""
        account = self._make_account()

        orders = [make_order(i, item_id=f"item-{i}", buyer_nick=f"buyer-{i}") for i in range(1, 201)]

        # 用真实 _prefetch_sync_lookups（FakeDb.execute 返回空），让主循环依赖空 map
        class FakeDb:
            def __init__(self):
                self.execute_calls = 0

            async def get(self, model, account_id):
                return account

            def add(self, item):
                pass

            async def execute(self, stmt):
                self.execute_calls += 1
                return FakeResult()

            async def flush(self):
                pass

        db = FakeDb()

        class FakeMtop:
            def __init__(self, cookie_str):
                self.cookie_str = cookie_str
                self.cookies_changed = False

        async def fake_fetch_orders(mtop, *, max_pages):
            return orders

        # mock upsert_order_mirror 为每单返回一个有效 mirror
        async def fake_upsert(db, account_id, order):
            from app.services.xianyu.order_parser import extract_order_no
            return SimpleNamespace(
                order_no=extract_order_no(order) or "unknown",
                projected_transaction_id=None,
            )

        # mock create_transaction 避免真实 DB 写入
        async def fake_create_transaction(db, **kwargs):
            return SimpleNamespace(id=1)

        # mock _ensure_customer：所有买家都返回同一个虚构客户（customer_map 应全部命中）
        shared_customer = SimpleNamespace(id=999, xianyu_nickname="shared")
        async def fake_ensure_customer(db, nickname, customer_map=None):
            if customer_map is not None:
                customer_map[nickname.strip().lower()] = shared_customer
            return shared_customer

        with (
            patch.object(order_service, "get_plain_cookies", return_value="cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
            patch.object(order_service, "upsert_order_mirror", side_effect=fake_upsert),
            patch.object(order_service, "create_transaction", side_effect=fake_create_transaction),
            patch.object(order_service, "_ensure_customer", side_effect=fake_ensure_customer),
            patch.object(order_service, "recalc_customer_stats"),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = await order_service.sync_orders_for_account(db, 1)

        # 关键断言：prefetch 阶段调用 db.execute 3 次（existing_tx / template / customer）
        # 主循环内不再有 db.execute 调用
        self.assertLessEqual(
            db.execute_calls,
            3,
            f"批量预取后 db.execute 调用次数应 ≤ 3，实际 {db.execute_calls}",
        )
        # 200 单应全部写入成功
        self.assertEqual(result["created_count"], 200)
        self.assertEqual(result["fetched"], 200)


if __name__ == "__main__":
    unittest.main()

