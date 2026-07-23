"""Manage and verify the packaged Alembic schema."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from app import models  # noqa: F401
from app.config import settings
from app.database import Base
from app.maintenance.database_backup import (
    create_backup,
    resolve_sqlite_path,
    verify_backup,
)
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
    missing_columns = {
        table: columns for table, columns in missing_columns.items() if columns
    }
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


def _create_pre_migration_backup(database_url: str) -> Path:
    source = resolve_sqlite_path(database_url)
    backup_dir = source.parent.parent / "backups"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"{source.stem}-pre-migration-{timestamp}.db"
    manifest = create_backup(source, destination)
    verify_backup(destination, manifest)
    print(f"迁移前备份已验证: {destination}")
    return destination


def migrate_database(database_url: str) -> None:
    """自动检测数据库状态并执行适当的迁移操作。

    用于容器入口脚本，确保数据库在任何状态下都能正确迁移到 head：

    - 全新数据库（无表）：upgrade 从头创建全部表
    - 已有数据库但无 alembic 版本（旧版 create_all 创建）：adopt 后 upgrade
    - 已有版本但不是 head：upgrade 到 head
    - 已在 head：无操作
    """
    _load_or_create_key()
    current, head = current_revision(database_url)

    if current == head:
        if head is not None:
            print(f"数据库已在最新版本: {head}")
        return

    engine = create_engine(sync_database_url(database_url))
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    if tables:
        _create_pre_migration_backup(database_url)

    if current is None:
        # 无版本表 — 可能是全新数据库或旧版 create_all 创建的数据库
        if tables:
            # 旧版数据库（有表但无版本管理）→ adopt
            print("检测到无版本管理的现有数据库，执行 adopt...")
            adopt_existing_database(database_url)
        else:
            # 全新数据库 → upgrade 从头创建
            print("检测到全新数据库，执行 upgrade 从头创建 schema...")
            command.upgrade(build_config(database_url), "head")
    else:
        # 有版本但不是 head → upgrade
        print(f"数据库版本 {current} 不是最新 {head}，执行 upgrade...")
        command.upgrade(build_config(database_url), "head")

    current, head = current_revision(database_url)
    if current != head:
        raise RuntimeError(
            f"迁移后版本仍不匹配: current={current!r}, head={head!r}"
        )
    print(f"迁移完成，当前版本: {head}")


async def require_current_schema(engine: AsyncEngine) -> None:
    config = build_config(str(engine.url))
    head = ScriptDirectory.from_config(config).get_current_head()
    async with engine.connect() as connection:
        current = await connection.run_sync(
            lambda sync_connection: MigrationContext.configure(
                sync_connection
            ).get_current_revision()
        )
    if current != head:
        raise RuntimeError(
            f"database revision mismatch: current={current!r}, expected={head!r}"
        )


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
    parser.add_argument("command", choices=("adopt", "upgrade", "current", "migrate"))
    args = parser.parse_args()
    database_url = settings.database_url
    if args.command == "adopt":
        _load_or_create_key()
        adopt_existing_database(database_url)
    elif args.command == "upgrade":
        _load_or_create_key()
        command.upgrade(build_config(database_url), "head")
    elif args.command == "migrate":
        migrate_database(database_url)
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
