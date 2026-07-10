# Xianyu Order Parser Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure Xianyu order payload parsing from `order_service.py` into a standard-library-only module without changing sync, persistence, API, or OpenAPI behavior.

**Architecture:** `order_parser.py` owns raw dictionary field extraction, response-list parsing, platform-status mapping, and time conversion. `order_service.py` remains the orchestration boundary for MTOP calls, authentication retry, database mirrors, transaction projection, locking, and sync logs, and imports parser functions explicitly.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest/unittest, Docker Compose

---

## File Structure

- Create `server/backend/app/services/xianyu/order_parser.py`: standard-library-only pure parser functions and platform status sets.
- Modify `server/backend/app/services/xianyu/order_service.py`: consume parser functions and remove duplicate parsing definitions.
- Create `server/backend/test_xianyu_order_parser.py`: parser behavior, ownership, and dependency-boundary tests.
- Modify `server/backend/test_order_service.py`: point existing parser assertions at the new parser boundary.

### Task 1: Establish the parser contract with failing tests

**Files:**
- Create: `server/backend/test_xianyu_order_parser.py`

- [ ] **Step 1: Write the failing parser contract test**

Create a unittest module that loads the desired module dynamically so the missing module produces an assertion failure rather than a collection error:

```python
import ast
import importlib
import importlib.util
import unittest
from datetime import datetime
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
        self.assertEqual(parser.parse_trade_time(order), datetime(2026, 7, 1, 12, 34, 56))
        self.assertEqual(parser.extract_shipped_time(order), datetime.utcfromtimestamp(1782900000))

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
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest server/backend/test_xianyu_order_parser.py -q
```

Expected: four assertion failures containing `order_parser module must exist`. A collection/import error is not an acceptable RED result.

- [ ] **Step 3: Commit the RED contract**

```powershell
git add -- server/backend/test_xianyu_order_parser.py
git commit -m "test: define xianyu order parser boundary"
```

### Task 2: Extract the pure parser and reconnect the service

**Files:**
- Create: `server/backend/app/services/xianyu/order_parser.py`
- Modify: `server/backend/app/services/xianyu/order_service.py`
- Modify: `server/backend/test_order_service.py`
- Test: `server/backend/test_xianyu_order_parser.py`
- Test: `server/backend/test_xianyu_order_mirror.py`
- Test: `server/backend/test_xianyu_order_projection.py`
- Test: `server/backend/test_xianyu_order_routes.py`

- [ ] **Step 1: Create the standard-library-only parser module**

Move the existing status sets and parsing logic verbatim, renaming the callable interface without leading underscores:

```python
"""Pure parsing helpers for raw Xianyu order payloads."""
from datetime import datetime
from typing import Optional

PENDING_PLATFORM_STATUSES = {"已付款", "待发货", "已发货", "待收货", "WAIT_SELLER_SEND_GOODS", "WAIT_BUYER_CONFIRM_GOODS", "SELLER_CONSIGNED_PART"}
COMPLETED_PLATFORM_STATUSES = {"交易成功", "交易完成", "部分退款成功", "SUCCESS", "TRADE_FINISHED", "COMPLETED", "PARTIAL_REFUND_SUCCESS"}
AFTERSALES_PLATFORM_STATUSES = {"退款中", "退款处理中", "售后中", "REFUNDING", "REFUND_PROCESSING", "TRADE_REFUNDING"}
CLOSED_PLATFORM_STATUSES = {"全额退款成功", "FULL_REFUND_SUCCESS"}
UNPROJECTED_PLATFORM_STATUSES = {"待付款", "待支付", "未付款关闭", "已关闭", "交易关闭", "WAIT_BUYER_PAY", "CLOSED", "TRADE_CLOSED", "TRADE_CLOSED_BY_TAOBAO"}


def extract_order_no(order: dict) -> Optional[str]:
    common_data = order.get("commonData")
    sources = (order, common_data) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in ("bizOrderId", "bizOderId", "orderId", "tradeId"):
            if source.get(key):
                return str(source[key])
    return None


def extract_price(order: dict) -> float:
    price_data = order.get("priceVO")
    sources = (order, price_data) if isinstance(price_data, dict) else (order,)
    for source in sources:
        for key in ("confirmFee", "actualFee", "realTotalPrice", "totalFee", "totalPrice"):
            value = source.get(key)
            if value is None:
                continue
            try:
                amount = float(value)
                if amount > 1000 and amount == int(amount):
                    return round(amount / 100, 2)
                return round(amount, 2)
            except (ValueError, TypeError):
                continue
    return 0.0


def extract_buyer_nick(order: dict) -> Optional[str]:
    buyer_info = order.get("buyerInfoVO")
    if isinstance(buyer_info, dict) and buyer_info.get("userNick"):
        return str(buyer_info["userNick"])
    for key in ("buyerNick", "buyer", "buyerName"):
        if order.get(key):
            return str(order[key])
    return None


def extract_product_name(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    if isinstance(item_info, dict) and item_info.get("title"):
        return str(item_info["title"])
    for key in ("title", "itemTitle"):
        if order.get(key):
            return str(order[key])
    return None


def extract_item_id(order: dict) -> Optional[str]:
    item_info = order.get("itemVO")
    sources = (item_info, order) if isinstance(item_info, dict) else (order,)
    for source in sources:
        for key in ("itemId", "item_id", "id", "fishId", "auctionId", "itemID"):
            if source.get(key):
                return str(source[key])
    return None


def extract_order_status(order: dict) -> Optional[str]:
    common_data = order.get("commonData")
    status = common_data.get("orderStatus") if isinstance(common_data, dict) else None
    status = status or order.get("orderStatus") or order.get("status")
    return str(status) if status else None


def _normalize_platform_status(status: str) -> str:
    return status.strip().upper().replace(" ", "_")


def project_transaction_status(order: dict) -> Optional[str]:
    status = extract_order_status(order)
    if not status:
        return "completed"
    normalized = _normalize_platform_status(status)
    if normalized in PENDING_PLATFORM_STATUSES:
        return "pending"
    if normalized in COMPLETED_PLATFORM_STATUSES:
        return "completed"
    if normalized in AFTERSALES_PLATFORM_STATUSES:
        return "aftersales"
    if normalized in CLOSED_PLATFORM_STATUSES:
        return "closed"
    if normalized in UNPROJECTED_PLATFORM_STATUSES:
        return None
    if "退款" in status and ("处理中" in status or "中" in status):
        return "aftersales"
    return None


def parse_orders(response: dict) -> list[dict]:
    if not isinstance(response, dict):
        return []
    for path in (("module", "items"), ("orders",), ("orderList",), ("result", "orders"), ("result", "orderList"), ("data",)):
        current: object = response
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, list):
                return current
    return []


def parse_trade_time(order: dict, *, fallback: Optional[datetime] = None) -> Optional[datetime]:
    return _parse_order_time(order, ("finishTime", "paySuccessTime", "createTime", "tradeTime", "gmtCreate", "payTime", "orderTime"), fallback=fallback)


def extract_shipped_time(order: dict) -> Optional[datetime]:
    return _parse_order_time(order, ("consignTime", "sellerShipTime", "shipTime", "sendTime", "deliveryTime", "gmtConsign", "gmtSend"))


def _parse_order_time(order: dict, keys: tuple[str, ...], *, fallback: Optional[datetime] = None) -> Optional[datetime]:
    common_data = order.get("commonData")
    sources = (common_data, order) if isinstance(common_data, dict) else (order,)
    for source in sources:
        for key in keys:
            value = source.get(key)
            if not value:
                continue
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    pass
            try:
                timestamp = float(value)
                if timestamp > 1e12:
                    timestamp /= 1000
                return datetime.utcfromtimestamp(timestamp)
            except (ValueError, TypeError):
                continue
    return fallback
```

- [ ] **Step 2: Reconnect `order_service.py` with explicit imports**

Remove its `datetime` import, platform status sets, and the ten parser function definitions. Add:

```python
from .order_parser import (
    extract_buyer_nick,
    extract_item_id,
    extract_order_no,
    extract_order_status,
    extract_price,
    extract_product_name,
    extract_shipped_time,
    parse_orders,
    parse_trade_time,
    project_transaction_status,
)
```

Replace internal calls exactly:

```text
_extract_order_no -> extract_order_no
_extract_price -> extract_price
_extract_buyer_nick -> extract_buyer_nick
_extract_product_name -> extract_product_name
_extract_item_id -> extract_item_id
_extract_order_status -> extract_order_status
_project_transaction_status -> project_transaction_status
_parse_orders -> parse_orders
_extract_shipped_time -> extract_shipped_time
_parse_trade_time(order) -> parse_trade_time(order, fallback=now_utc())
```

Keep `_apply_order_projection_to_transaction` in the service and make its completed branch call `extract_shipped_time(order)`. Do not change any surrounding control flow.

- [ ] **Step 3: Migrate existing parser assertions to the new owner**

In `test_order_service.py`, import `order_parser` beside `order_service` and replace calls to `_parse_orders`, `_extract_order_no`, `_extract_price`, `_extract_buyer_nick`, `_extract_product_name`, `_parse_trade_time`, and `_project_transaction_status` with their public `order_parser` equivalents. Keep sync orchestration tests on `order_service`.

- [ ] **Step 4: Run parser and order tests and verify GREEN**

```powershell
python -m pytest server/backend/test_xianyu_order_parser.py server/backend/test_order_service.py server/backend/test_xianyu_order_mirror.py server/backend/test_xianyu_order_projection.py server/backend/test_xianyu_order_routes.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run source hygiene checks**

```powershell
rg -n '^def (_extract_|_parse_orders|_parse_trade_time|_project_transaction_status)' server/backend/app/services/xianyu/order_service.py
git diff --check
```

Expected: `rg` finds no duplicate parser definitions; `git diff --check` exits successfully.

- [ ] **Step 6: Commit the extraction**

```powershell
git add -- server/backend/app/services/xianyu/order_parser.py server/backend/app/services/xianyu/order_service.py server/backend/test_order_service.py
git commit -m "refactor: isolate xianyu order parsing"
```

### Task 3: Run complete regression and runtime verification

**Files:**
- Verify only; no source changes expected.

- [ ] **Step 1: Run the full backend suite**

```powershell
python -m pytest server/backend -q
```

Expected: all backend tests and subtests pass; only the existing datetime deprecation warnings may remain.

- [ ] **Step 2: Run the full frontend suite, type check, and build**

```powershell
npm test -- --run
npm run check
npm run build
```

Expected: 130 frontend tests pass, type check passes, and production build succeeds; existing `use client` and chunk-size warnings may remain.

- [ ] **Step 3: Rebuild and smoke-test the backend container**

```powershell
docker compose up -d --build backend
```

Verify HTTP 200 from `/api/health`, `/api/xianyu/accounts`, `/api/xianyu/accounts/{known-account-id}/orders`, and `/openapi.json`. Use a read-only account-list response to choose an existing account id; do not create or modify data.

- [ ] **Step 4: Verify schema revision and recovery point**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: current and head are both `20260710_02`; backup verification succeeds.

- [ ] **Step 5: Confirm clean implementation state**

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: no uncommitted workspace changes and the design, plan, RED-test, and implementation commits are visible.
