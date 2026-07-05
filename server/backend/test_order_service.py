import unittest
import warnings
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.xianyu import order_service


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
            order_service._parse_orders({"module": {"items": orders}}),
            orders,
        )

    def test_extractors_support_current_nested_fields(self):
        order = make_order(1001)

        self.assertEqual(order_service._extract_order_no(order), "1001")
        self.assertEqual(order_service._extract_price(order), 88.0)
        self.assertEqual(order_service._extract_buyer_nick(order), "测试买家")
        self.assertEqual(order_service._extract_product_name(order), "测试商品")
        self.assertEqual(
            order_service._parse_trade_time(order),
            datetime(2026, 7, 1, 12, 34, 56),
        )

    def test_only_completed_orders_are_importable(self):
        self.assertTrue(order_service._is_completed_order(make_order(1001)))
        self.assertFalse(
            order_service._is_completed_order(
                make_order(1002, status="交易关闭"),
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
    async def test_sync_persists_refreshed_cookies(self):
        account = SimpleNamespace(
            cookies="encrypted-old",
            status="online",
            last_error=None,
            last_sync_at=None,
            updated_at=None,
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


if __name__ == "__main__":
    unittest.main()
