# Xianyu Item Parser Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure Xianyu item payload parsing from `item_service.py` into a standard-library-only module without changing fetch, mirror, template import, authentication, API, or OpenAPI behavior.

**Architecture:** `item_parser.py` owns raw card unwrapping, field and price extraction, list response parsing, and user-id extraction. `item_service.py` remains the orchestration boundary for MTOP pagination, CookieCloud retry, database mirrors, and product-template projection.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest/unittest, Docker Compose

---

## File Structure

- Create `server/backend/app/services/xianyu/item_parser.py`: standard-library-only pure item parser functions.
- Modify `server/backend/app/services/xianyu/item_service.py`: consume parser functions and remove duplicate parsing definitions.
- Create `server/backend/test_xianyu_item_parser.py`: parser behavior, ownership, dependency, and source-boundary tests.

### Task 1: Establish the parser contract with failing tests

**Files:**
- Create: `server/backend/test_xianyu_item_parser.py`

- [ ] **Step 1: Write the failing parser contract**

```python
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
        self.assertEqual(parser.extract_image_url(item), "https://example.test/item.png")

    def test_preserves_price_cleanup_and_invalid_fallback(self):
        parser = self.load_parser()
        self.assertEqual(parser.extract_price({"price": "¥88.50"}), 88.5)
        self.assertEqual(parser.extract_price({"price": "1,250"}), 12.5)
        self.assertEqual(parser.extract_price({"price": "invalid"}), 0.0)

    def test_parses_item_lists_and_user_id_paths(self):
        parser = self.load_parser()
        item = {"id": "ITEM-1"}
        self.assertEqual(parser.parse_items({"module": {"cardList": [item, "bad"]}}), [item])
        self.assertEqual(parser.parse_items({"unexpected": [item]}), [])
        self.assertEqual(parser.extract_user_id({"module": {"base": {"uid": 123}}}), "123")
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
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest server/backend/test_xianyu_item_parser.py -q
```

Expected: four assertion failures containing `item_parser module must exist`; collection errors are not acceptable.

- [ ] **Step 3: Commit the RED contract**

```powershell
git add -- server/backend/test_xianyu_item_parser.py
git commit -m "test: define xianyu item parser boundary"
```

### Task 2: Extract the pure parser and reconnect the service

**Files:**
- Create: `server/backend/app/services/xianyu/item_parser.py`
- Modify: `server/backend/app/services/xianyu/item_service.py`
- Test: `server/backend/test_xianyu_item_parser.py`
- Test: `server/backend/test_xianyu_item_service.py`
- Test: `server/backend/test_xianyu_item_routes.py`

- [ ] **Step 1: Create the pure parser module**

```python
"""Pure parsing helpers for raw Xianyu item payloads."""
from typing import Any, Optional


def _nested(source: dict, *path: str) -> Any:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("price", "priceText", "value", "amount", "cent"):
            price = _coerce_price(value.get(key))
            if price is not None:
                return price
        return None
    text = str(value).strip().replace("¥", "").replace("￥", "").replace(",", "")
    if not text:
        return None
    try:
        amount = float(text)
    except ValueError:
        return None
    if amount > 1000 and amount == int(amount):
        return round(amount / 100, 2)
    return round(amount, 2)


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _unwrap_item(item: dict) -> dict:
    for key in ("cardData", "item", "itemDO", "itemVO", "itemInfo", "data", "detailParams"):
        nested = item.get(key)
        if isinstance(nested, dict):
            return {**item, **nested}
    return item


def extract_item_id(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(data.get("itemId"), data.get("item_id"), data.get("id"), data.get("fishId"), data.get("auctionId"), data.get("itemID"))


def extract_title(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(data.get("title"), data.get("itemTitle"), data.get("name"), data.get("subject"), _nested(data, "titleInfo", "title"))


def extract_price(item: dict) -> float:
    data = _unwrap_item(item)
    for value in (data.get("price"), data.get("soldPrice"), data.get("currentPrice"), data.get("reservePrice"), _nested(data, "priceInfo", "price"), _nested(data, "priceInfo", "priceText"), _nested(data, "priceVO", "price"), _nested(data, "priceVO", "realPrice")):
        price = _coerce_price(value)
        if price is not None:
            return price
    return 0.0


def extract_status(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(data.get("itemStatus"), data.get("status"), data.get("statusText"), data.get("publishStatus"), data.get("soldStatus"))


def extract_image_url(item: dict) -> Optional[str]:
    data = _unwrap_item(item)
    return _first_text(data.get("picUrl"), data.get("image"), data.get("itemPicUrl"), data.get("cover"), _nested(data, "picInfo", "picUrl"), _nested(data, "imageInfo", "url"))


def parse_items(response: dict) -> list[dict]:
    if not isinstance(response, dict):
        return []
    for path in (("module", "items"), ("module", "list"), ("module", "itemList"), ("module", "cardList"), ("cardList",), ("items",), ("itemList",), ("list",), ("result", "items"), ("result", "itemList"), ("data",)):
        current: Any = response
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, list):
                return [item for item in current if isinstance(item, dict)]
    return []


def extract_user_id(response: dict) -> Optional[str]:
    for path in (("module", "base", "userId"), ("module", "base", "uid"), ("module", "userId"), ("base", "userId"), ("userId",)):
        text = _first_text(_nested(response, *path))
        if text:
            return text
    return None
```

- [ ] **Step 2: Reconnect `item_service.py`**

Change its typing import to `from typing import Optional`, delete the private pure parser functions, and add:

```python
from .item_parser import (
    extract_image_url,
    extract_item_id,
    extract_price,
    extract_status,
    extract_title,
    extract_user_id,
    parse_items,
)
```

Replace calls exactly:

```text
_extract_item_id -> extract_item_id
_extract_title -> extract_title
_extract_price -> extract_price
_extract_status -> extract_status
_extract_image_url -> extract_image_url
_parse_items -> parse_items
_extract_user_id -> extract_user_id
```

Keep `_fetch_user_id`, pagination, sync retry, mirror persistence, and template import control flow unchanged.

- [ ] **Step 3: Run focused tests and verify GREEN**

```powershell
python -m pytest server/backend/test_xianyu_item_parser.py server/backend/test_xianyu_item_service.py server/backend/test_xianyu_item_routes.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Verify source hygiene**

```powershell
rg -n '^def (_nested|_coerce_price|_first_text|_unwrap_item|_extract_item|_extract_title|_extract_price|_extract_status|_extract_image_url|_parse_items|_extract_user_id)' server/backend/app/services/xianyu/item_service.py
git diff --check
```

Expected: no duplicate parser definitions and no whitespace errors.

- [ ] **Step 5: Commit the implementation**

```powershell
git add -- server/backend/app/services/xianyu/item_parser.py server/backend/app/services/xianyu/item_service.py
git commit -m "refactor: isolate xianyu item parsing"
```

### Task 3: Run complete regression and runtime verification

**Files:**
- Verify only; no source changes expected.

- [ ] **Step 1: Run backend regression**

```powershell
python -m pytest server/backend -q
```

Expected: all backend tests and subtests pass; only existing datetime deprecation warnings may remain.

- [ ] **Step 2: Run frontend verification**

```powershell
npm test -- --run
npm run check
npm run build
```

Expected: 130 frontend tests pass, type check passes, and production build succeeds; existing Vite warnings may remain.

- [ ] **Step 3: Rebuild and smoke-test backend**

```powershell
docker compose up -d --build backend
```

Verify HTTP 200 from `/api/health`, `/api/xianyu/accounts`, `/api/xianyu/accounts/{existing-id}/items`, and `/openapi.json`. Obtain the id from the read-only account list and do not print account payloads.

- [ ] **Step 4: Verify schema revision and backup**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: current=head=`20260710_02` and backup verification succeeds.

- [ ] **Step 5: Confirm clean state**

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: clean workspace with design, plan, RED-test, and implementation commits visible.
