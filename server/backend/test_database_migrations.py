import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
from app import models  # noqa: F401
from app.maintenance.database_schema import adopt_existing_database, require_current_schema


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


def test_adopt_existing_database_stamps_baseline_and_upgrades(tmp_path):
    database = tmp_path / "existing.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    adopt_existing_database(sync_url)

    async_engine = create_async_engine(
        sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    )
    asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())


def test_adopt_rejects_database_with_missing_required_column(tmp_path):
    database = tmp_path / "drifted.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE customers (id INTEGER PRIMARY KEY)")
    engine.dispose()

    with pytest.raises(RuntimeError, match="schema does not match required baseline"):
        adopt_existing_database(f"sqlite:///{database.as_posix()}")


def test_revision_guard_rejects_unversioned_database(tmp_path):
    database = tmp_path / "unversioned.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    async_engine = create_async_engine(
        sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    )

    with pytest.raises(RuntimeError, match="database revision mismatch"):
        asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())
