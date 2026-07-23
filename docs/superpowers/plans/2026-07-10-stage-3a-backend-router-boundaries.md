# Stage 3A Backend Router Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the six domains currently mixed in `routers/settings.py` into focused FastAPI router modules without changing the public API or transaction behavior.

**Architecture:** Keep the existing flat `routers/` convention and make every module export one `router`. Protect the refactor with an exact method/path characterization test plus source-boundary assertions, then register each router explicitly in `main.py`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest, httpx ASGITransport, Docker Compose.

---

## File map

- Create `server/backend/test_router_boundaries.py`: exact API surface and source boundary tests.
- Keep `server/backend/app/routers/settings.py`: settings endpoints only, exported as `router`.
- Create `server/backend/app/routers/product_templates.py`: product template CRUD/toggle.
- Create `server/backend/app/routers/finance.py`: finance overview, rankings, trend, comparison, customer counts.
- Create `server/backend/app/routers/expenses.py`: operating expense CRUD.
- Create `server/backend/app/routers/audit.py`: operation log list/clear.
- Create `server/backend/app/routers/migrate.py`: backup import/export.
- Modify `server/backend/app/main.py`: explicit module imports and router registration.

### Task 1: Characterize the route surface and create a failing source boundary

**Files:**
- Create: `server/backend/test_router_boundaries.py`

- [ ] **Step 1: Write the route contract and boundary test**

Create `server/backend/test_router_boundaries.py`:

```python
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app


ROUTER_DIR = Path(__file__).parent / "app" / "routers"
MAIN = Path(__file__).parent / "app" / "main.py"

EXPECTED_ROUTES = {
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("GET", "/api/product-templates"),
    ("POST", "/api/product-templates"),
    ("PATCH", "/api/product-templates/{tpl_id}"),
    ("DELETE", "/api/product-templates/{tpl_id}"),
    ("POST", "/api/product-templates/{tpl_id}/toggle"),
    ("GET", "/api/finance/overview"),
    ("GET", "/api/finance/products"),
    ("GET", "/api/finance/customers"),
    ("GET", "/api/finance/overview-by-range"),
    ("GET", "/api/finance/trend"),
    ("GET", "/api/finance/monthly-comparison"),
    ("GET", "/api/finance/new-customer-count"),
    ("GET", "/api/expenses"),
    ("POST", "/api/expenses"),
    ("PATCH", "/api/expenses/{expense_id}"),
    ("DELETE", "/api/expenses/{expense_id}"),
    ("GET", "/api/operation-logs"),
    ("DELETE", "/api/operation-logs"),
    ("POST", "/api/migrate/import"),
    ("GET", "/api/migrate/export"),
}


def test_split_domain_route_surface_is_preserved():
    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if any(
            route.path.startswith(prefix)
            for prefix in (
                "/api/settings",
                "/api/product-templates",
                "/api/finance",
                "/api/expenses",
                "/api/operation-logs",
                "/api/migrate",
            )
        )
    }
    assert actual == EXPECTED_ROUTES


def test_each_domain_has_one_router_module():
    expected_files = {
        "settings.py",
        "product_templates.py",
        "finance.py",
        "expenses.py",
        "audit.py",
        "migrate.py",
    }
    assert expected_files <= {path.name for path in ROUTER_DIR.glob("*.py")}

    settings_source = (ROUTER_DIR / "settings.py").read_text(encoding="utf-8")
    for forbidden in (
        "/api/product-templates",
        "/api/finance",
        "/api/expenses",
        "/api/operation-logs",
        "/api/migrate",
        "product_template_service",
        "finance_service",
        "expense_service",
        "audit_service",
        "migrate_service",
    ):
        assert forbidden not in settings_source

    main_source = MAIN.read_text(encoding="utf-8")
    assert "settings_router_module" not in main_source
```

- [ ] **Step 2: Run the test and verify the intended mixed result**

Run:

```powershell
python -m pytest server/backend/test_router_boundaries.py -q
```

Expected: route-surface test passes; module/source-boundary test fails because five files do not exist and `settings.py` contains other domains.

### Task 2: Create product template and expense routers

**Files:**
- Create: `server/backend/app/routers/product_templates.py`
- Create: `server/backend/app/routers/expenses.py`

- [ ] **Step 1: Create `product_templates.py`**

```python
"""Product template routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import ProductTemplateCreate, ProductTemplateOut, ProductTemplateUpdate
from ..services import product_template_service

router = APIRouter(prefix="/api/product-templates", tags=["product-templates"])


@router.get("", response_model=list[ProductTemplateOut])
async def list_templates(active_only: bool = Query(False), db: AsyncSession = Depends(get_db)):
    items = (
        await product_template_service.list_active_templates(db)
        if active_only
        else await product_template_service.list_templates(db)
    )
    await db.commit()
    return items


@router.post("", response_model=ProductTemplateOut)
async def create_template(payload: ProductTemplateCreate, db: AsyncSession = Depends(get_db)):
    template = await product_template_service.create_template(db, **payload.model_dump())
    await db.commit()
    return template


@router.patch("/{tpl_id}", response_model=ProductTemplateOut)
async def update_template(tpl_id: int, payload: ProductTemplateUpdate, db: AsyncSession = Depends(get_db)):
    try:
        template = await product_template_service.update_template(
            db, tpl_id, payload.model_dump(exclude_unset=True)
        )
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{tpl_id}")
async def delete_template(tpl_id: int, db: AsyncSession = Depends(get_db)):
    await product_template_service.delete_template(db, tpl_id)
    await db.commit()
    return {"message": "已删除"}


@router.post("/{tpl_id}/toggle", response_model=ProductTemplateOut)
async def toggle_active(tpl_id: int, db: AsyncSession = Depends(get_db)):
    try:
        template = await product_template_service.toggle_active(db, tpl_id)
        await db.commit()
        return template
    except ValueError as exc:
        raise HTTPException(404, str(exc))
```

- [ ] **Step 2: Create `expenses.py`**

```python
"""Operating expense routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import OperatingExpenseCreate, OperatingExpenseOut, OperatingExpenseUpdate
from ..services import expense_service
from ..utils.helpers import parse_date

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[OperatingExpenseOut])
async def list_expenses(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await expense_service.list_expenses(
        db,
        parse_date(start) if start else None,
        parse_date(end) if end else None,
    )
    await db.commit()
    return data


@router.post("", response_model=OperatingExpenseOut)
async def create_expense(payload: OperatingExpenseCreate, db: AsyncSession = Depends(get_db)):
    data = await expense_service.create_expense(db, **payload.model_dump())
    await db.commit()
    return data


@router.patch("/{expense_id}", response_model=OperatingExpenseOut)
async def update_expense(
    expense_id: int,
    payload: OperatingExpenseUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await expense_service.update_expense(
            db, expense_id, payload.model_dump(exclude_unset=True)
        )
        await db.commit()
        return data
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await expense_service.delete_expense(db, expense_id)
        await db.commit()
        return {"message": "已删除"}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
```

### Task 3: Split finance, audit, and migrate routers

**Files:**
- Create: `server/backend/app/routers/finance.py`
- Create: `server/backend/app/routers/audit.py`
- Create: `server/backend/app/routers/migrate.py`

- [ ] **Step 1: Create `finance.py`**

Implement the same seven `/api/finance` handlers with the existing Query limits. Import `parse_date` at module scope and preserve every commit:

```python
"""Finance reporting routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import finance_service
from ..utils.helpers import parse_date

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/overview")
async def finance_overview(db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_finance_overview(db)
    await db.commit()
    return data


@router.get("/products")
async def product_profit_stats(
    start: Optional[str] = Query(None), end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_product_profit_stats(
        db, parse_date(start) if start else None, parse_date(end) if end else None
    )
    await db.commit()
    return data


@router.get("/customers")
async def customer_value_stats(limit: int = Query(100), db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_customer_value_stats(db, limit)
    await db.commit()
    return data


@router.get("/overview-by-range")
async def finance_overview_by_range(
    start: str = Query(...), end: str = Query(...), db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_finance_overview_by_range(
        db, parse_date(start), parse_date(end)
    )
    await db.commit()
    return data


@router.get("/trend")
async def trend(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    data = await finance_service.get_trend(db, days)
    await db.commit()
    return data


@router.get("/monthly-comparison")
async def monthly_comparison(
    months: int = Query(6, ge=1, le=24), db: AsyncSession = Depends(get_db),
):
    data = await finance_service.get_monthly_comparison(db, months)
    await db.commit()
    return data


@router.get("/new-customer-count")
async def new_customer_count(
    start: Optional[str] = Query(None), end: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    count = (
        await finance_service.get_new_customer_count_by_range(
            db, parse_date(start), parse_date(end)
        )
        if start and end
        else await finance_service.get_new_customer_count(db)
    )
    await db.commit()
    return {"count": count}
```

- [ ] **Step 2: Create `audit.py`**

```python
"""Operation audit log routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import LogListResponse
from ..services import audit_service

router = APIRouter(prefix="/api/operation-logs", tags=["audit"])


@router.get("", response_model=LogListResponse)
async def list_logs(
    module: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_service.list_logs(
        db, module=module, limit=page_size, offset=(page - 1) * page_size
    )
    await db.commit()
    return {"items": items, "total": total}


@router.delete("")
async def clear_logs(db: AsyncSession = Depends(get_db)):
    await audit_service.clear_logs(db)
    await db.commit()
    return {"message": "日志已清空"}
```

- [ ] **Step 3: Create `migrate.py`**

```python
"""JSON backup import and export routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import MigrateImportResponse
from ..services import migrate_service

router = APIRouter(prefix="/api/migrate", tags=["migrate"])


@router.post("/import", response_model=MigrateImportResponse)
async def import_backup(backup: dict, db: AsyncSession = Depends(get_db)):
    try:
        counts = await migrate_service.import_backup(db, backup)
        await db.commit()
        return MigrateImportResponse(counts=counts, message="导入成功")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/export")
async def export_backup(db: AsyncSession = Depends(get_db)):
    data = await migrate_service.export_backup(db)
    await db.commit()
    return data
```

### Task 4: Register focused routers and make the boundary GREEN

**Files:**
- Modify: `server/backend/app/main.py`
- Modify: `server/backend/app/routers/settings.py`
- Test: `server/backend/test_router_boundaries.py`

- [ ] **Step 1: Reduce `settings.py` to its single responsibility**

Replace it with:

```python
"""System settings routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import SettingsOut, SettingsUpdate
from ..services import settings_service
from ..services.settings_service import SettingsError

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    data = await settings_service.get_settings_plain(db)
    await db.commit()
    return data


@router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    try:
        await settings_service.update_settings(db, payload.model_dump(exclude_unset=True))
        await db.commit()
        data = await settings_service.get_settings_plain(db)
        await db.commit()
        return data
    except SettingsError as exc:
        raise HTTPException(400, str(exc))
```

- [ ] **Step 2: Replace indirect settings module registration**

In `main.py`, import the six modules directly in the existing routers tuple:

```python
settings,
product_templates,
finance,
expenses,
audit,
migrate,
```

Replace the six `settings_router_module.*_router` calls with:

```python
app.include_router(settings.router)
app.include_router(product_templates.router)
app.include_router(finance.router)
app.include_router(expenses.router)
app.include_router(audit.router)
app.include_router(migrate.router)
```

- [ ] **Step 3: Run the boundary and focused behavior tests**

```powershell
python -m pytest server/backend/test_router_boundaries.py server/backend/test_settings_routes.py server/backend/test_product_template_routes.py server/backend/test_expense_finance_service.py -q
```

Expected: all tests pass; exact route surface matches and source boundary is satisfied.

- [ ] **Step 4: Run the full backend suite**

```powershell
python -m pytest server/backend -q
```

Expected: 73 tests plus existing subtests pass with only pre-existing datetime deprecation warnings.

- [ ] **Step 5: Commit the refactor and tests**

```powershell
git add -- server/backend/app/main.py server/backend/app/routers/settings.py server/backend/app/routers/product_templates.py server/backend/app/routers/finance.py server/backend/app/routers/expenses.py server/backend/app/routers/audit.py server/backend/app/routers/migrate.py server/backend/test_router_boundaries.py
git commit -m "refactor: split backend domain routers"
```

### Task 5: Runtime verification and memory closeout

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

Expected: frontend tests, TypeScript, production build, and all backend tests pass. Existing Vite `use client` and chunk-size warnings are acceptable.

- [ ] **Step 2: Rebuild backend and verify routes at runtime**

```powershell
docker compose up -d --build backend
docker ps --filter name=xianyugou
```

Then request these non-mutating endpoints and require HTTP 200:

```text
GET http://localhost:18001/api/health
GET http://localhost:18001/api/settings
GET http://localhost:18001/api/product-templates
GET http://localhost:18001/api/finance/overview
GET http://localhost:18001/api/expenses
GET http://localhost:18001/api/operation-logs
GET http://localhost:18001/api/migrate/export
```

- [ ] **Step 3: Verify schema, backup, and clean worktree**

```powershell
docker exec xianyugou-backend python -m app.maintenance.database_schema current
docker exec xianyugou-backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
git status --short
```

Expected: current=head=`20260710_02`, backup verified, worktree clean.

- [ ] **Step 4: Update persistent project memory**

Append a concise Stage 3A record to `E:\Obsidian\Codex\projects\XianyuGou.md` with the boundary decision, commit IDs, test counts, runtime verification, and next substage. Do not record response bodies or business data.
