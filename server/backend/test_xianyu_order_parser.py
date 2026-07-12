import ast
import importlib
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


PARSER_MODULE = "app.services.xianyu.order_parser"
PARSER_PATH = Path(__file__).parent / "app" / "services" / "xianyu" / "order_parser.py"
PUBLIC_FUNCTIONS = {
    "extract_order_no",
    "extract_price",
    "extract_buyer_nick",
    "extract_product_name",
    "extract_item_id",
    "extract_order_status",
    "project_transaction_status",
    "parse_orders",
    "parse_trade_time",
    "extract_shipped_time",
}


class XianyuOrderParserTests(unittest.TestCase):
    def load_parser(self):
        spec = importlib.util.find_spec(PARSER_MODULE)
        self.assertIsNotNone(spec, "order_parser module must exist")
        module = importlib.import_module(PARSER_MODULE)
        missing = PUBLIC_FUNCTIONS - set(vars(module))
        self.assertEqual(missing, set())
        return module

    def test_extracts_nested_order_fields_and_cent_price(self):
        parser = self.load_parser()
        order = {
            "commonData": {"orderId": "ORDER-1", "orderStatus": "待发货"},
            "buyerInfoVO": {"userNick": "buyer-a"},
            "itemVO": {"itemId": "ITEM-1", "title": "product-a"},
            "priceVO": {"confirmFee": 12345},
        }
        self.assertEqual(parser.extract_order_no(order), "ORDER-1")
        self.assertEqual(parser.extract_order_status(order), "待发货")
        self.assertEqual(parser.extract_buyer_nick(order), "buyer-a")
        self.assertEqual(parser.extract_item_id(order), "ITEM-1")
        self.assertEqual(parser.extract_product_name(order), "product-a")
        self.assertEqual(parser.extract_price(order), 123.45)

    def test_maps_platform_statuses_without_changing_existing_rules(self):
        parser = self.load_parser()
        cases = {
            None: "completed",
            "已付款": "pending",
            "TRADE_FINISHED": "completed",
            "退款处理中": "aftersales",
            "全额退款成功": "closed",
            "WAIT_BUYER_PAY": None,
            "未知状态": None,
        }
        for status, expected in cases.items():
            order = {} if status is None else {"status": status}
            with self.subTest(status=status):
                self.assertEqual(parser.project_transaction_status(order), expected)

    def test_parses_response_paths_and_order_times(self):
        parser = self.load_parser()
        orders = [{"orderId": "ORDER-1"}]
        self.assertIs(parser.parse_orders({"module": {"items": orders}}), orders)
        self.assertEqual(parser.parse_orders({"unexpected": orders}), [])
        order = {
            "commonData": {
                "finishTime": "2026-07-01T12:34:56",
                "consignTime": 1782900000000,
            }
        }
        self.assertEqual(
            parser.parse_trade_time(order),
            datetime(2026, 7, 1, 12, 34, 56),
        )
        self.assertEqual(
            parser.extract_shipped_time(order),
            datetime.fromtimestamp(1782900000, timezone.utc).replace(tzinfo=None),
        )

    def test_parser_has_standard_library_dependencies_and_owns_functions(self):
        parser = self.load_parser()
        tree = ast.parse(PARSER_PATH.read_text(encoding="utf-8"))
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertLessEqual(imported_roots, {"datetime", "typing"})
        for name in PUBLIC_FUNCTIONS:
            self.assertEqual(getattr(parser, name).__module__, PARSER_MODULE)


if __name__ == "__main__":
    unittest.main()
