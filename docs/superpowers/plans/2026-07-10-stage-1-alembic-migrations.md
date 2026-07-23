# Stage 1 Alembic Migration System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace startup-time `create_all` and handwritten SQLite `ALTER TABLE` statements with explicit Alembic versions while safely adopting the existing Docker database.

**Architecture:** Alembic lives under `app/migrations` so the existing backend Dockerfile copies it without unrelated edits. A generated baseline revision creates a new database; a second idempotent compatibility revision fills indexes that legacy `ALTER TABLE` operations could not create. Existing databases are adopted only after required tables and columns are verified, while normal application startup performs a read-only head-revision check.

**Tech Stack:** Python 3.9+, Alembic 1.13.2, SQLAlchemy 2.0 async/sync engines, SQLite, pytest, Docker Compose.

---

## File map

- Modify `.gitignore`: ignore local Playwright CLI artifacts discovered in the valid working baseline.
- Modify `server/backend/requirements.txt`: pin Alembic.
- Create `server/backend/app/migrations/alembic.ini`: Alembic configuration packaged inside `app`.
- Create `server/backend/app/migrations/env.py`: load current ORM metadata and convert the async SQLite URL for synchronous migrations.
- Create `server/backend/app/migrations/script.py.mako`: deterministic revision template.
- Create `server/backend/app/migrations/versions/20260710_01_current_schema_baseline.py`: generated current-schema baseline.
- Create `server/backend/app/migrations/versions/20260710_02_legacy_index_reconciliation.py`: idempotent legacy index reconciliation.
- Create `server/backend/app/maintenance/database_schema.py`: config builder, existing-schema validation, adopt/upgrade/current CLI, and startup revision guard.
- Create `server/backend/test_database_migrations.py`: empty-database, adoption, drift rejection, and revision-guard tests.
- Modify `server/backend/app/database.py`: keep session setup but replace implicit DDL with the revision guard.
- Modify `server/backend/README.md`: migration and rollback runbook.

### Task 0: Capture the user-approved application baseline

**Files:**
- Modify: `.gitignore`
- Commit: all current tracked and untracked source/test/config changes except ignored runtime artifacts.

- [ ] **Step 1: Ignore Playwright CLI runtime output**

Add under editor/tool output in `.gitignore`:

```gitignore
.playwright-cli/
```

- [ ] **Step 2: Verify the baseline is safe to commit**

Run:

```powershell
git diff --check
git status --short
rg -n "(SECRET_KEY|COOKIE|TOKEN|PASSWORD)\s*=\s*[^$\{].+" .env.example server/backend -g '!data/**' -g '!backups/**'
```

Expected: no whitespace errors; `.playwright-cli/` and backups are ignored; the scan finds only variable declarations, test sentinels, or empty/example values, never usable credentials.

- [ ] **Step 3: Stage the approved baseline**

```powershell
git add -A -- .
git diff --cached --name-only
git diff --cached --check
```

Expected: application source, tests, configuration, `.env.example`, and lockfile changes are staged; `.playwright-cli/`, runtime databases, backup files, `secret.key`, Cookies and Tokens are absent.

- [ ] **Step 4: Commit the baseline**

```powershell
git commit -m "chore: capture current application baseline"
```

### Task 1: Scaffold Alembic and generate the baseline revision

**Files:**
- Modify: `server/backend/requirements.txt`
- Create: `server/backend/app/migrations/alembic.ini`
- Create: `server/backend/app/migrations/env.py`
- Create: `server/backend/app/migrations/script.py.mako`
- Create: `server/backend/app/migrations/versions/20260710_01_current_schema_baseline.py`

- [ ] **Step 1: Pin Alembic**

Append to `requirements.txt`:

```text
alembic==1.13.2
```

- [ ] **Step 2: Add packaged Alembic configuration**

Create `app/migrations/alembic.ini`:

```ini
[alembic]
script_location = %(here)s
prepend_sys_path = %(here)s/../..
path_separator = os
sqlalchemy.url = sqlite:///placeholder.db

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `app/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base
from app import models  # noqa: F401


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def migration_url() -> str:
    configured = config.attributes.get("database_url", settings.database_url)
    if not configured.startswith("sqlite"):
        raise RuntimeError("Alembic migrations currently support SQLite only")
    return configured.replace("sqlite+aiosqlite", "sqlite", 1)


def run_migrations_offline() -> None:
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = migration_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `app/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Generate the deterministic baseline against an empty temporary database**

From `server/backend` run:

```powershell
$tempDb = Join-Path $env:TEMP 'xianyugou-alembic-empty.db'
Remove-Item -LiteralPath $tempDb -ErrorAction SilentlyContinue
$env:DATABASE_URL = "sqlite+aiosqlite:///$($tempDb.Replace('\','/'))"
alembic -c app/migrations/alembic.ini revision --autogenerate --rev-id 20260710_01 -m "current schema baseline"
Remove-Item Env:DATABASE_URL
Remove-Item -LiteralPath $tempDb -ErrorAction SilentlyContinue
```

Expected: `20260710_01_current_schema_baseline.py` contains `op.create_table` and `op.create_index` calls for every table in `Base.metadata`; it contains no data values or credentials.

- [ ] **Step 4: Add a generated-revision smoke test**

Create `test_database_migrations.py` with:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.database import Base
from app import models  # noqa: F401


MIGRATIONS = Path(__file__).parent / "app" / "migrations"


def migration_config(database_url: str) -> Config:
    config = Config(str(MIGRATIONS / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def test_empty_database_upgrades_to_current_metadata(tmp_path):
    database = tmp_path / "empty.db"
    url = f"sqlite:///{database.as_posix()}"

    command.upgrade(migration_config(url), "head")

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert tables == set(Base.metadata.tables) | {"alembic_version"}
```

- [ ] **Step 5: Run the migration test**

```powershell
python -m pytest server/backend/test_database_migrations.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit scaffold and generated baseline**

```powershell
git add -- server/backend/requirements.txt server/backend/app/migrations server/backend/test_database_migrations.py
git commit -m "feat: add alembic schema baseline"
```

### Task 2: Add safe existing-database adoption and revision checks

**Files:**
- Create: `server/backend/app/migrations/versions/20260710_02_legacy_index_reconciliation.py`
- Create: `server/backend/app/maintenance/database_schema.py`
- Modify: `server/backend/test_database_migrations.py`

- [ ] **Step 1: Add failing adoption and guard tests**

Append tests that:

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.maintenance.database_schema import adopt_existing_database, require_current_schema


def test_adopt_existing_database_stamps_baseline_and_upgrades(tmp_path):
    database = tmp_path / "existing.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    adopt_existing_database(sync_url)

    async_engine = create_async_engine(sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1))
    asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())


def test_adopt_rejects_database_with_missing_required_column(tmp_path):
    database = tmp_path / "drifted.db"
    with create_engine(f"sqlite:///{database.as_posix()}").begin() as connection:
        connection.exec_driver_sql("CREATE TABLE customers (id INTEGER PRIMARY KEY)")

    with pytest.raises(RuntimeError, match="schema does not match required baseline"):
        adopt_existing_database(f"sqlite:///{database.as_posix()}")


def test_revision_guard_rejects_unversioned_database(tmp_path):
    database = tmp_path / "unversioned.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    async_engine = create_async_engine(sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1))

    with pytest.raises(RuntimeError, match="database revision mismatch"):
        asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())
```

Also add `import pytest` to the test file.

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest server/backend/test_database_migrations.py -q
```

Expected: import fails because `app.maintenance.database_schema` does not exist.

- [ ] **Step 3: Add the compatibility revision**

Create revision `20260710_02` with `down_revision = "20260710_01"`. Its `upgrade()` executes these SQLite-safe statements:

```python
op.execute("CREATE INDEX IF NOT EXISTS ix_product_templates_source_xianyu_account_id ON product_templates (source_xianyu_account_id)")
op.execute("CREATE INDEX IF NOT EXISTS ix_product_templates_source_xianyu_item_id ON product_templates (source_xianyu_item_id)")
op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_shipped_at ON transactions (shipped_at)")
```

Its `downgrade()` uses `DROP INDEX IF EXISTS` for the same three index names.

- [ ] **Step 4: Implement adoption and the read-only revision guard**

In `database_schema.py`, implement:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings
from app.database import Base
from app import models  # noqa: F401
from app.utils.crypto import _load_or_create_key


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
BASELINE_REVISION = "20260710_01"


def sync_database_url(database_url: str) -> str:
    if not database_url.startswith("sqlite"):
        raise RuntimeError("database schema management currently supports SQLite only")
    return database_url.replace("sqlite+aiosqlite", "sqlite", 1)


def build_config(database_url: str | None = None) -> Config:
    config = Config(str(MIGRATIONS / "alembic.ini"))
    config.attributes["database_url"] = database_url or settings.database_url
    return config


def _validate_required_schema(database_url: str) -> None:
    engine = create_engine(sync_database_url(database_url))
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)
    missing_tables = sorted(expected_tables - actual_tables)
    missing_columns = {
        table: sorted(
            set(Base.metadata.tables[table].columns.keys())
            - {column["name"] for column in inspector.get_columns(table)}
        )
        for table in sorted(expected_tables & actual_tables)
    }
    engine.dispose()
    missing_columns = {table: columns for table, columns in missing_columns.items() if columns}
    if missing_tables or missing_columns:
        raise RuntimeError(
            "schema does not match required baseline: "
            f"missing_tables={missing_tables}, missing_columns={missing_columns}"
        )


def adopt_existing_database(database_url: str) -> None:
    _validate_required_schema(database_url)
    config = build_config(database_url)
    command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


async def require_current_schema(engine: AsyncEngine) -> None:
    config = build_config(str(engine.url))
    head = ScriptDirectory.from_config(config).get_current_head()
    async with engine.connect() as connection:
        current = await connection.run_sync(
            lambda sync_connection: MigrationContext.configure(sync_connection).get_current_revision()
        )
    if current != head:
        raise RuntimeError(f"database revision mismatch: current={current!r}, expected={head!r}")
```

Append the CLI implementation:

```python
def current_revision(database_url: str) -> tuple[str | None, str | None]:
    config = build_config(database_url)
    head = ScriptDirectory.from_config(config).get_current_head()
    engine = create_engine(sync_database_url(database_url))
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    engine.dispose()
    return current, head


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the packaged database schema")
    parser.add_argument("command", choices=("adopt", "upgrade", "current"))
    args = parser.parse_args()
    database_url = settings.database_url
    if args.command == "adopt":
        _load_or_create_key()
        adopt_existing_database(database_url)
    elif args.command == "upgrade":
        _load_or_create_key()
        command.upgrade(build_config(database_url), "head")
    else:
        current, head = current_revision(database_url)
        print(f"current={current or 'unversioned'}")
        print(f"head={head or 'none'}")
        return 0 if current == head else 1
    current, head = current_revision(database_url)
    print(f"current={current or 'unversioned'}")
    print(f"head={head or 'none'}")
    return 0 if current == head else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

The CLI reports only revision identifiers, never database URLs, paths, field values, or credentials.

- [ ] **Step 5: Run focused tests and verify GREEN**

```powershell
python -m pytest server/backend/test_database_migrations.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit adoption and revision guard**

```powershell
git add -- server/backend/app/migrations/versions/20260710_02_legacy_index_reconciliation.py server/backend/app/maintenance/database_schema.py server/backend/test_database_migrations.py
git commit -m "feat: guard and adopt database revisions"
```

### Task 3: Remove implicit startup DDL

**Files:**
- Modify: `server/backend/app/database.py`
- Modify: `server/backend/test_database_migrations.py`

- [ ] **Step 1: Add a failing source regression test**

```python
def test_application_startup_contains_no_implicit_schema_ddl():
    source = (Path(__file__).parent / "app" / "database.py").read_text(encoding="utf-8")

    assert "Base.metadata.create_all" not in source
    assert "ALTER TABLE" not in source
    assert "_ensure_sqlite_columns" not in source
    assert "require_current_schema" in source
```

- [ ] **Step 2: Run and verify RED**

```powershell
python -m pytest server/backend/test_database_migrations.py::test_application_startup_contains_no_implicit_schema_ddl -q
```

Expected: fails because the current `database.py` still contains implicit DDL.

- [ ] **Step 3: Replace `init_db` implementation**

Keep `Base`, `engine`, `AsyncSessionLocal`, and `get_db`. Remove the `text` import and `_ensure_sqlite_columns`. Implement:

```python
async def init_db() -> None:
    """Verify that the operator-managed database is at the packaged Alembic head."""
    from .config import DEFAULT_DB_PATH
    from .maintenance.database_schema import require_current_schema

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    await require_current_schema(engine)
```

- [ ] **Step 4: Run migration and backend regression tests**

```powershell
python -m pytest server/backend/test_database_migrations.py server/backend/test_security_baseline.py -q
python -m pytest server/backend -q
```

Expected: all tests pass; test fixtures may continue using `Base.metadata.create_all` for isolated in-memory databases.

- [ ] **Step 5: Commit startup guard**

```powershell
git add -- server/backend/app/database.py server/backend/test_database_migrations.py
git commit -m "refactor: require alembic head at startup"
```

### Task 4: Adopt the real database and verify deployment

**Files:**
- Modify: `server/backend/README.md`
- Runtime: ignored backup files and Docker volume only.

- [ ] **Step 1: Reverify the pre-Alembic backup**

```powershell
docker compose exec backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: `Backup verified`.

- [ ] **Step 2: Build the backend image without replacing the running container**

```powershell
docker compose build backend
```

- [ ] **Step 3: Adopt and upgrade the existing database in a one-off container**

```powershell
docker compose run --rm backend python -m app.maintenance.database_schema adopt
```

Expected: required table/column validation passes, the database is stamped at `20260710_01`, upgraded to `20260710_02`, and no business rows are printed or modified.

- [ ] **Step 4: Replace the backend container and verify revision**

```powershell
docker compose up -d backend
docker compose exec backend python -m app.maintenance.database_schema current
```

Expected: backend is Up and current revision equals `20260710_02`.

- [ ] **Step 5: Document operator workflow**

Add a README section with exact commands for:

```powershell
# Existing verified database, one time only
docker compose run --rm backend python -m app.maintenance.database_schema adopt

# New database or later migration
docker compose run --rm backend python -m app.maintenance.database_schema upgrade

# Read-only status
docker compose exec backend python -m app.maintenance.database_schema current
```

State that `adopt` is allowed only after a verified backup and refuses missing tables/columns; application startup never runs migrations.

- [ ] **Step 6: Run final verification**

```powershell
python -m pytest server/backend -q
npm test -- --run
npm run build
docker compose ps
git diff --check
```

Verify HTTP 200 for the web root, backend `/api/health`, and mail `/api/health`. Reverify the backup after deployment.

- [ ] **Step 7: Commit the migration runbook**

```powershell
git add -- server/backend/README.md
git commit -m "docs: add database migration runbook"
```

## Stage 1 completion gate

- Current user changes are preserved in an explicit baseline commit.
- Empty databases upgrade through Alembic to the complete ORM schema.
- Existing databases are validated before adoption and reconciled through `20260710_02`.
- Application startup contains no `create_all`, handwritten `ALTER TABLE`, or automatic migration.
- Unknown, missing, or stale revisions block startup.
- The real database remains readable, the pre-Alembic backup verifies, and all services remain healthy.
- Full backend tests, frontend tests, build, Compose status, and HTTP health checks pass.
