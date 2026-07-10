# Stage 3B Schema Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 400-line `app/schemas.py` module with domain-focused schema modules while preserving every existing public import and Pydantic contract.

**Architecture:** Create an `app/schemas/` package with one shared base module, eleven domain modules, one common response module, and an explicit compatibility facade. Existing routers keep importing from `app.schemas`, so this is an internal-only structural refactor.

**Tech Stack:** Python 3.11, Pydantic 2, FastAPI, pytest, Docker Compose.

---

## File map

- Create `server/backend/test_schema_boundaries.py`: package ownership, public export, field constraint, and OpenAPI tests.
- Create `server/backend/app/schemas/base.py`: `ORMBase` only.
- Create `server/backend/app/schemas/customers.py`: three customer schemas.
- Create `server/backend/app/schemas/transactions.py`: transaction schemas and `StatusChange`.
- Create `server/backend/app/schemas/aftersales.py`: three after-sales schemas.
- Create `server/backend/app/schemas/rebates.py`: three rebate schemas.
- Create `server/backend/app/schemas/expenses.py`: three operating expense schemas.
- Create `server/backend/app/schemas/product_templates.py`: three product template schemas.
- Create `server/backend/app/schemas/settings.py`: two settings schemas.
- Create `server/backend/app/schemas/audit.py`: audit item and list response.
- Create `server/backend/app/schemas/migrate.py`: migrate import response.
- Create `server/backend/app/schemas/attachments.py`: attachment metadata and batch request.
- Create `server/backend/app/schemas/xianyu.py`: twelve Xianyu/CookieCloud schemas.
- Create `server/backend/app/schemas/common.py`: message and health responses.
- Create `server/backend/app/schemas/__init__.py`: exact compatibility exports.
- Delete `server/backend/app/schemas.py`: remove the duplicate definition source.

### Task 1: Add a failing schema package boundary test

**Files:**
- Create: `server/backend/test_schema_boundaries.py`

- [ ] **Step 1: Write public export and ownership tests**

Create this test:

```python
from pathlib import Path

import app.schemas as schemas
from app.main import app


APP_DIR = Path(__file__).parent / "app"

EXPECTED_EXPORTS = {
    "ORMBase",
    "CustomerOut", "CustomerCreate", "CustomerUpdate",
    "TransactionOut", "TransactionCreate", "TransactionUpdate", "StatusChange",
    "AfterSalesOut", "AfterSalesCreate", "AfterSalesUpdate",
    "RebateOut", "RebateStatusChange", "RebateBatchPay",
    "OperatingExpenseOut", "OperatingExpenseCreate", "OperatingExpenseUpdate",
    "ProductTemplateOut", "ProductTemplateCreate", "ProductTemplateUpdate",
    "SettingsOut", "SettingsUpdate",
    "OperationLogOut", "LogListResponse",
    "MigrateImportResponse",
    "AttachmentOut", "AttachmentBatchRequest",
    "XianyuAccountCreate", "XianyuAccountUpdate", "XianyuAccountOut",
    "XianyuAccountTestResult", "CookieCloudConfigStatus", "XianyuSyncResult",
    "XianyuItemSyncResult", "XianyuItemOut", "XianyuItemImportRequest",
    "XianyuItemImportResult", "XianyuOrderOut",
    "MessageResponse", "HealthResponse",
}

EXPECTED_MODULES = {
    "CustomerOut": "app.schemas.customers",
    "TransactionOut": "app.schemas.transactions",
    "AfterSalesOut": "app.schemas.aftersales",
    "RebateOut": "app.schemas.rebates",
    "OperatingExpenseOut": "app.schemas.expenses",
    "ProductTemplateOut": "app.schemas.product_templates",
    "SettingsOut": "app.schemas.settings",
    "OperationLogOut": "app.schemas.audit",
    "MigrateImportResponse": "app.schemas.migrate",
    "AttachmentOut": "app.schemas.attachments",
    "XianyuAccountOut": "app.schemas.xianyu",
    "HealthResponse": "app.schemas.common",
}


def test_schema_package_has_exact_compatibility_exports():
    assert set(schemas.__all__) == EXPECTED_EXPORTS
    assert all(hasattr(schemas, name) for name in EXPECTED_EXPORTS)
    assert not (APP_DIR / "schemas.py").exists()


def test_schema_classes_belong_to_domain_modules():
    for name, module in EXPECTED_MODULES.items():
        assert getattr(schemas, name).__module__ == module


def test_critical_field_constraints_are_preserved():
    expense_schema = schemas.OperatingExpenseCreate.model_json_schema()
    template_schema = schemas.ProductTemplateCreate.model_json_schema()
    attachment_schema = schemas.AttachmentBatchRequest.model_json_schema()

    assert expense_schema["properties"]["amount"]["exclusiveMinimum"] == 0
    assert template_schema["properties"]["warranty_days"]["minimum"] == 0
    assert attachment_schema["properties"]["ids"]["maxItems"] == 50


def test_fastapi_openapi_still_builds_with_public_schema_names():
    components = app.openapi()["components"]["schemas"]
    for name in (
        "CustomerOut",
        "TransactionOut",
        "SettingsOut",
        "AttachmentOut",
        "XianyuAccountOut",
    ):
        assert name in components
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest server/backend/test_schema_boundaries.py -q
```

Expected: collection or assertion failure because `schemas` is still a module, has no `__all__`, and classes report `app.schemas` as their module.

### Task 2: Create the shared base and core commerce schema modules

**Files:**
- Create: `server/backend/app/schemas/base.py`
- Create: `server/backend/app/schemas/customers.py`
- Create: `server/backend/app/schemas/transactions.py`
- Create: `server/backend/app/schemas/aftersales.py`
- Create: `server/backend/app/schemas/rebates.py`

- [ ] **Step 1: Create the shared base**

```python
from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Move core schemas without changing fields**

Create the four domain modules with these exact class ownership lists and imports:

```text
customers.py
  imports: datetime; List, Optional; BaseModel; ORMBase
  classes: CustomerOut, CustomerCreate, CustomerUpdate

transactions.py
  imports: datetime; List, Optional; BaseModel; ORMBase
  classes: TransactionOut, TransactionCreate, TransactionUpdate, StatusChange

aftersales.py
  imports: datetime; List, Optional; BaseModel; ORMBase
  classes: AfterSalesOut, AfterSalesCreate, AfterSalesUpdate

rebates.py
  imports: datetime; List, Optional; BaseModel; ORMBase
  classes: RebateOut, RebateStatusChange, RebateBatchPay
```

Copy each listed class body byte-for-byte from `schemas.py`; only imports and section comments may change. In every module import the base as:

```python
from .base import ORMBase
```

Do not replace `List[...]`, mutable list defaults, Optional annotations, or field order.

### Task 3: Create finance, settings, operations, and attachment modules

**Files:**
- Create: `server/backend/app/schemas/expenses.py`
- Create: `server/backend/app/schemas/product_templates.py`
- Create: `server/backend/app/schemas/settings.py`
- Create: `server/backend/app/schemas/audit.py`
- Create: `server/backend/app/schemas/migrate.py`
- Create: `server/backend/app/schemas/attachments.py`

- [ ] **Step 1: Create six focused modules**

Use these exact ownership and import rules:

```text
expenses.py
  imports: datetime; Optional; BaseModel, Field; ORMBase
  classes: OperatingExpenseOut, OperatingExpenseCreate, OperatingExpenseUpdate

product_templates.py
  imports: datetime; Optional; BaseModel, Field; ORMBase
  classes: ProductTemplateOut, ProductTemplateCreate, ProductTemplateUpdate

settings.py
  imports: Optional; BaseModel; ORMBase
  classes: SettingsOut, SettingsUpdate

audit.py
  imports: datetime; List, Optional; BaseModel; ORMBase
  classes: OperationLogOut, LogListResponse

migrate.py
  imports: BaseModel
  classes: MigrateImportResponse

attachments.py
  imports: datetime; List; BaseModel, Field; ORMBase
  classes: AttachmentOut, AttachmentBatchRequest
```

Copy each class body exactly from the old module. Preserve all `Field` arguments, including expense amount `gt=0`, warranty `ge=0`, and attachment list `max_length=50`.

### Task 4: Create Xianyu and common modules, then publish the facade

**Files:**
- Create: `server/backend/app/schemas/xianyu.py`
- Create: `server/backend/app/schemas/common.py`
- Create: `server/backend/app/schemas/__init__.py`
- Delete: `server/backend/app/schemas.py`

- [ ] **Step 1: Create `xianyu.py` and `common.py`**

`xianyu.py` imports `datetime`, `Optional`, `BaseModel`, `Field`, and `ORMBase`; it contains exactly:

```text
XianyuAccountCreate
XianyuAccountUpdate
XianyuAccountOut
XianyuAccountTestResult
CookieCloudConfigStatus
XianyuSyncResult
XianyuItemSyncResult
XianyuItemOut
XianyuItemImportRequest
XianyuItemImportResult
XianyuOrderOut
```

`common.py` imports `Any`, `Optional`, and `BaseModel`; it contains `MessageResponse` and `HealthResponse`. Copy all fields and defaults exactly.

- [ ] **Step 2: Create the explicit compatibility facade**

Create `schemas/__init__.py` with explicit imports from every domain module and this exact `__all__` order:

```python
__all__ = [
    "ORMBase",
    "CustomerOut", "CustomerCreate", "CustomerUpdate",
    "TransactionOut", "TransactionCreate", "TransactionUpdate", "StatusChange",
    "AfterSalesOut", "AfterSalesCreate", "AfterSalesUpdate",
    "RebateOut", "RebateStatusChange", "RebateBatchPay",
    "OperatingExpenseOut", "OperatingExpenseCreate", "OperatingExpenseUpdate",
    "ProductTemplateOut", "ProductTemplateCreate", "ProductTemplateUpdate",
    "SettingsOut", "SettingsUpdate",
    "OperationLogOut", "LogListResponse",
    "MigrateImportResponse",
    "AttachmentOut", "AttachmentBatchRequest",
    "XianyuAccountCreate", "XianyuAccountUpdate", "XianyuAccountOut",
    "XianyuAccountTestResult", "CookieCloudConfigStatus", "XianyuSyncResult",
    "XianyuItemSyncResult", "XianyuItemOut", "XianyuItemImportRequest",
    "XianyuItemImportResult", "XianyuOrderOut",
    "MessageResponse", "HealthResponse",
]
```

Every name in the list must have a matching explicit `from .<domain> import ...` statement above it. Do not use wildcard imports.

- [ ] **Step 3: Delete the old module**

Delete `server/backend/app/schemas.py` only after all package files and the facade exist. Do not modify any router imports.

### Task 5: Verify the package boundary and commit

**Files:**
- Test: `server/backend/test_schema_boundaries.py`
- Test: `server/backend/test_router_boundaries.py`

- [ ] **Step 1: Run the schema and route boundary tests**

```powershell
python -m pytest server/backend/test_schema_boundaries.py server/backend/test_router_boundaries.py -q
```

Expected: 6 tests pass; exact exports, module ownership, constraints, OpenAPI, and route surface are preserved.

- [ ] **Step 2: Run focused route tests**

```powershell
python -m pytest server/backend/test_settings_routes.py server/backend/test_product_template_routes.py server/backend/test_attachment_routes.py server/backend/test_xianyu_account_routes.py server/backend/test_xianyu_item_routes.py server/backend/test_xianyu_order_routes.py -q
```

Expected: all focused route tests pass.

- [ ] **Step 3: Run the full backend suite**

```powershell
python -m pytest server/backend -q
```

Expected: 77 tests plus existing subtests pass with only pre-existing datetime deprecation warnings.

- [ ] **Step 4: Commit**

```powershell
git add -- server/backend/app/schemas server/backend/test_schema_boundaries.py
git rm -- server/backend/app/schemas.py
git commit -m "refactor: split backend schema domains"
```

### Task 6: Full and runtime verification

**Files:**
- Modify only if verification exposes a defect caused by this refactor.

- [ ] **Step 1: Run repository verification**

```powershell
npm test -- --run
npm run check
npm run build
python -m pytest server/backend -q
git diff --check
```

Expected: frontend tests, TypeScript, production build, and all backend tests pass.

- [ ] **Step 2: Rebuild backend and verify representative endpoints**

```powershell
docker compose up -d --build backend
docker ps --filter name=xianyugou
```

Require HTTP 200 from:

```text
GET /api/health
GET /api/settings
GET /api/transactions
GET /api/attachments/batch is not used because it is POST; verify it through tests only
GET /api/xianyu/accounts
GET /openapi.json
```

- [ ] **Step 3: Verify schema, backup, and clean worktree**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
git status --short
```

Expected: current=head=`20260710_02`, backup verified, worktree clean.

- [ ] **Step 4: Update persistent project memory**

Append Stage 3B decisions, commits, verification counts, and next substage to `E:\Obsidian\Codex\projects\XianyuGou.md`. Do not record response bodies or business data.
