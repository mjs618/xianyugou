"""Manage and verify the packaged Alembic schema."""
from __future__ import annotations

import argparse
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
