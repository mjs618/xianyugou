# Stage 0 Baseline Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested, repeatable SQLite backup and verification workflow, then capture a clean application baseline before any database migration work begins.

**Architecture:** A small Python maintenance module uses SQLite's online backup API to create a consistent database copy, writes a non-sensitive manifest containing checksums and table counts, and verifies integrity without opening or printing encrypted values. The workflow does not change application startup or business behavior.

**Tech Stack:** Python 3.9+, stdlib `sqlite3`/`hashlib`/`argparse`, pytest, FastAPI project configuration, npm/Vitest/Vite, Docker Compose.

---

## File map

- Create `server/backend/app/maintenance/__init__.py`: maintenance package marker.
- Create `server/backend/app/maintenance/database_backup.py`: SQLite path parsing, online backup, manifest generation, verification, and CLI.
- Create `server/backend/test_database_backup.py`: focused tests for copy consistency, manifest contents, tamper detection, and CLI behavior.
- Modify `server/backend/README.md`: operator commands and recovery boundaries.
- Modify `.gitignore`: prevent generated backup artifacts from entering Git.

### Task 1: Define backup behavior with failing tests

**Files:**
- Create: `server/backend/test_database_backup.py`

- [ ] **Step 1: Write path and backup tests**

Create the test file with these imports, helpers, and tests:

```python
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.maintenance.database_backup import (
    BackupError,
    create_backup,
    resolve_sqlite_path,
    verify_backup,
)


def create_source_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("CREATE TABLE transactions (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL)")
        connection.execute("INSERT INTO customers (name) VALUES ('测试客户')")
        connection.execute("INSERT INTO transactions (customer_id) VALUES (1)")
        connection.commit()


def test_resolve_sqlite_path_accepts_absolute_async_url(tmp_path):
    database = tmp_path / "source.db"

    result = resolve_sqlite_path(f"sqlite+aiosqlite:///{database.as_posix()}")

    assert result == database.resolve()


def test_resolve_sqlite_path_rejects_non_sqlite_url():
    with pytest.raises(BackupError, match="only supports SQLite"):
        resolve_sqlite_path("mysql+asyncmy://user:pass@localhost/app")


def test_create_and_verify_backup(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "backups" / "snapshot.db"
    create_source_database(source)

    manifest_path = create_backup(source, destination)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert destination.exists()
    assert manifest_path == destination.with_suffix(".manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["database_file"] == destination.name
    assert manifest["integrity_check"] == "ok"
    assert manifest["table_counts"] == {"customers": 1, "transactions": 1}
    assert "secret" not in json.dumps(manifest).lower()
    verify_backup(destination, manifest_path)


def test_verify_backup_detects_modified_database(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    create_source_database(source)
    manifest_path = create_backup(source, destination)

    with sqlite3.connect(destination) as connection:
        connection.execute("INSERT INTO customers (name) VALUES ('篡改数据')")
        connection.commit()

    with pytest.raises(BackupError, match="checksum mismatch"):
        verify_backup(destination, manifest_path)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest server/backend/test_database_backup.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.maintenance'`.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add -- server/backend/test_database_backup.py
git commit -m "test: define database backup contract"
```

### Task 2: Implement consistent SQLite backups

**Files:**
- Create: `server/backend/app/maintenance/__init__.py`
- Create: `server/backend/app/maintenance/database_backup.py`

- [ ] **Step 1: Add the maintenance package marker**

```python
"""Offline maintenance tools for the local deployment."""
```

- [ ] **Step 2: Implement backup creation and verification**

Create `database_backup.py` with this implementation:

```python
"""Create and verify consistent SQLite backups without exposing business data."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.config import settings


class BackupError(RuntimeError):
    """Raised when a backup cannot be created or verified safely."""


def resolve_sqlite_path(database_url: str) -> Path:
    normalized = database_url.replace("sqlite+aiosqlite", "sqlite", 1)
    parsed = urlparse(normalized)
    if parsed.scheme != "sqlite":
        raise BackupError("database backup only supports SQLite")
    if not parsed.path or parsed.path == "/:memory:":
        raise BackupError("database backup requires a file-backed SQLite database")
    raw_path = unquote(parsed.path)
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect(path: Path) -> tuple[str, dict[str, int]]:
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        counts = {
            str(name): int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for (name,) in rows
        }
    return integrity, counts


def create_backup(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise BackupError("source database does not exist")
    if destination.exists():
        raise BackupError("backup destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(source) as source_connection:
            with sqlite3.connect(temporary) as backup_connection:
                source_connection.backup(backup_connection)
        temporary.replace(destination)
        integrity, table_counts = _inspect(destination)
        if integrity != "ok":
            raise BackupError("backup integrity check failed")
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_file": destination.name,
            "sha256": _sha256(destination),
            "integrity_check": integrity,
            "table_counts": table_counts,
        }
        manifest_path = destination.with_suffix(".manifest.json")
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path
    except Exception:
        temporary.unlink(missing_ok=True)
        if destination.exists() and not destination.with_suffix(".manifest.json").exists():
            destination.unlink()
        raise


def verify_backup(database: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise BackupError("unsupported backup manifest version")
    if manifest.get("database_file") != database.name:
        raise BackupError("backup filename mismatch")
    if manifest.get("sha256") != _sha256(database):
        raise BackupError("backup checksum mismatch")
    integrity, counts = _inspect(database)
    if integrity != "ok":
        raise BackupError("backup integrity check failed")
    if manifest.get("table_counts") != counts:
        raise BackupError("backup table counts mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify an SQLite backup")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--database", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            source = resolve_sqlite_path(settings.database_url)
            manifest = create_backup(source, args.output)
            print(f"Backup verified: {args.output.resolve()}")
            print(f"Manifest: {manifest.resolve()}")
        else:
            verify_backup(args.database.resolve(), args.manifest.resolve())
            print(f"Backup verified: {args.database.resolve()}")
        return 0
    except (BackupError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
```

- [ ] **Step 3: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest server/backend/test_database_backup.py -q
```

Expected: `4 passed`.

- [ ] **Step 4: Run backend regression tests**

Run:

```powershell
python -m pytest server/backend -q
```

Expected: all backend tests pass; existing `datetime.utcnow()` deprecation warnings are allowed.

- [ ] **Step 5: Commit the implementation**

```powershell
git add -- server/backend/app/maintenance/__init__.py server/backend/app/maintenance/database_backup.py
git commit -m "feat: add verified sqlite backups"
```

### Task 3: Test the command-line contract

**Files:**
- Modify: `server/backend/test_database_backup.py`

- [ ] **Step 1: Add CLI tests**

Append these tests:

```python
def test_cli_create_and_verify(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    create_source_database(source)
    database_url = f"sqlite+aiosqlite:///{source.as_posix()}"

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.maintenance.database_backup",
            "create",
            "--output",
            str(destination),
        ],
        cwd=Path(__file__).parent,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0
    assert "Backup verified:" in created.stdout

    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.maintenance.database_backup",
            "verify",
            "--database",
            str(destination),
            "--manifest",
            str(destination.with_suffix(".manifest.json")),
        ],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0
    assert "Backup verified:" in verified.stdout


def test_cli_does_not_overwrite_existing_backup(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    create_source_database(source)
    destination.write_bytes(b"existing")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.maintenance.database_backup",
            "create",
            "--output",
            str(destination),
        ],
        cwd=Path(__file__).parent,
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite+aiosqlite:///{source.as_posix()}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "backup destination already exists" in result.stderr
    assert destination.read_bytes() == b"existing"
```

Also add `import os` beside the existing standard-library imports.

- [ ] **Step 2: Run CLI integration tests**

Run:

```powershell
python -m pytest server/backend/test_database_backup.py -q
```

Expected: `6 passed`. These tests exercise the command-line boundary of the already implemented backup contract; they do not introduce new production behavior.

- [ ] **Step 3: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest server/backend/test_database_backup.py -q
```

Expected: `6 passed`.

- [ ] **Step 4: Commit CLI coverage**

```powershell
git add -- server/backend/test_database_backup.py
git commit -m "test: cover database backup cli"
```

### Task 4: Document and ignore backup artifacts

**Files:**
- Modify: `.gitignore`
- Modify: `server/backend/README.md`

- [ ] **Step 1: Add the backup directory to `.gitignore`**

Append under the database entries:

```gitignore
/server/backend/backups/
```

- [ ] **Step 2: Add operator documentation**

Append this section to `server/backend/README.md`:

````markdown
## 数据库备份与校验

结构迁移或镜像升级前，先进入 `server/backend` 目录，创建带校验清单的 SQLite 备份：

```powershell
python -m app.maintenance.database_backup create --output backups/xianyu-YYYYMMDD-HHMMSS.db
```

该命令使用 SQLite 在线备份 API，不覆盖已有文件，并生成同名 `.manifest.json`，其中只包含校验和、表名和记录数，不包含业务字段值或密钥。

恢复前先校验备份：

```powershell
python -m app.maintenance.database_backup verify --database backups/xianyu-YYYYMMDD-HHMMSS.db --manifest backups/xianyu-YYYYMMDD-HHMMSS.manifest.json
```

数据库与 `data/secret.key` 必须配套保存。工具不会复制或打印密钥。实际恢复涉及覆盖运行数据库，必须先停止后端并由操作者明确执行；本工具只负责创建和校验备份。
````

- [ ] **Step 3: Verify ignore and documentation**

Run:

```powershell
git check-ignore server/backend/backups/sample.db
rg -n "数据库备份与校验|database_backup|secret.key" server/backend/README.md
```

Expected: the sample backup path is ignored and the new documentation is found.

- [ ] **Step 4: Run all automated verification**

Run:

```powershell
python -m pytest server/backend -q
npm test -- --run
npm run build
git diff --check
```

Expected: backend tests pass, frontend tests pass, build exits `0`, and `git diff --check` has no output.

- [ ] **Step 5: Commit documentation and ignore rules**

```powershell
git add -- .gitignore server/backend/README.md
git commit -m "docs: add database backup runbook"
```

### Task 5: Capture the Stage 0 operational baseline

**Files:**
- Verify only; do not commit generated database or manifest files.

- [ ] **Step 1: Record current worktree without changing it**

Run:

```powershell
git status --short
git log -5 --oneline --decorate
```

Expected: existing user changes remain present and no unrelated file is staged.

- [ ] **Step 2: Create a real backup without printing secrets**

From `server/backend`, choose a unique timestamped destination and run:

```powershell
python -m app.maintenance.database_backup create --output backups/xianyu-20260710-pre-alembic.db
```

Expected: the command reports the database and manifest paths, never prints field values or key contents, and refuses to overwrite an existing destination.

- [ ] **Step 3: Verify the real backup**

Run:

```powershell
python -m app.maintenance.database_backup verify --database backups/xianyu-20260710-pre-alembic.db --manifest backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: `Backup verified` and exit code `0`.

- [ ] **Step 4: Verify services**

Run:

```powershell
docker compose ps
```

Then verify HTTP status `200` for:

```text
http://localhost:15173/
http://localhost:18001/api/health
http://localhost:13001/api/health
```

Expected: `web`, `backend`, and `mail` are running and all three endpoints respond successfully.

- [ ] **Step 5: Confirm generated backup artifacts remain untracked**

Run:

```powershell
git status --short --ignored server/backend/backups
```

Expected: backup files are shown only as ignored (`!!`), never staged or tracked.

## Stage 0 completion gate

Do not begin the Alembic plan until all of the following are true:

- Six backup tests pass.
- The full backend and frontend suites pass.
- The frontend production build succeeds.
- A real pre-Alembic backup and manifest verify successfully.
- Existing user changes remain intact.
- Docker services and health endpoints are operational.
- No database, backup, key, Cookie, Token, or credential is tracked by Git.
