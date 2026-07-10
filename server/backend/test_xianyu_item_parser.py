import ast
import importlib
import importlib.util
import unittest
from pathlib import Path


PARSER_MODULE = "app.services.xianyu.item_parser"
PARSER_PATH = Path(__file__).parent / "app" / "services" / "xianyu" / "item_parser.py"
SERVICE_PATH = Path(__file__).parent / "app" / "services" / "xianyu" / "item_service.py"
PUBLIC_FUNCTIONS = {
    "extract_item_id",
    "extract_title",
    "extract_price",
    "extract_status",
    "extract_image_url",
    "parse_items",
    "extract_user_id",
}


class XianyuItemParserTests(unittest.TestCase):
    def load_parser(self):
        spec = importlib.util.find_spec(PARSER_MODULE)
        self.assertIsNotNone(spec, "item_parser module must exist")
        module = importlib.import_module(PARSER_MODULE)
        self.assertEqual(PUBLIC_FUNCTIONS - set(vars(module)), set())
        return module

    def test_extracts_nested_card_fields_and_cent_price(self):
        parser = self.load_parser()
        item = {
            "cardType": 1,
            "cardData": {
                "id": "ITEM-1",
                "title": "账号商品",
                "itemStatus": 0,
                "priceInfo": {"price": 12345},
                "picInfo": {"picUrl": "https://example.test/item.png"},
            },
        }
        self.assertEqual(parser.extract_item_id(item), "ITEM-1")
        self.assertEqual(parser.extract_title(item), "账号商品")
        self.assertEqual(parser.extract_price(item), 123.45)
        self.assertEqual(parser.extract_status(item), "0")
        self.assertEqual(
            parser.extract_image_url(item),
            "https://example.test/item.png",
        )

    def test_preserves_price_cleanup_and_invalid_fallback(self):
        parser = self.load_parser()
        self.assertEqual(parser.extract_price({"price": "¥88.50"}), 88.5)
        self.assertEqual(parser.extract_price({"price": "1,250"}), 12.5)
        self.assertEqual(parser.extract_price({"price": "invalid"}), 0.0)

    def test_parses_item_lists_and_user_id_paths(self):
        parser = self.load_parser()
        item = {"id": "ITEM-1"}
        self.assertEqual(
            parser.parse_items({"module": {"cardList": [item, "bad"]}}),
            [item],
        )
        self.assertEqual(parser.parse_items({"unexpected": [item]}), [])
        self.assertEqual(
            parser.extract_user_id({"module": {"base": {"uid": 123}}}),
            "123",
        )
        self.assertIsNone(parser.extract_user_id({"module": {}}))

    def test_parser_owns_functions_and_has_only_standard_library_dependencies(self):
        parser = self.load_parser()
        tree = ast.parse(PARSER_PATH.read_text(encoding="utf-8"))
        imported_roots = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertLessEqual(imported_roots, {"typing"})
        for name in PUBLIC_FUNCTIONS:
            self.assertEqual(getattr(parser, name).__module__, PARSER_MODULE)
        service_tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
        service_defs = {
            node.name for node in service_tree.body if isinstance(node, ast.FunctionDef)
        }
        self.assertFalse(
            service_defs
            & {
                "_extract_item_id",
                "_extract_title",
                "_extract_price",
                "_extract_status",
                "_extract_image_url",
                "_parse_items",
                "_extract_user_id",
            }
        )


if __name__ == "__main__":
    unittest.main()
