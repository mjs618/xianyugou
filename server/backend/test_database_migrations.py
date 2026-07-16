import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
from app import models  # noqa: F401
from app.maintenance import database_schema
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


def test_migrate_database_on_fresh_database(tmp_path):
    """migrate 对全新数据库执行 upgrade 从头创建 schema。"""
    from app.maintenance.database_schema import migrate_database

    database = tmp_path / "fresh.db"
    sync_url = f"sqlite:///{database.as_posix()}"

    migrate_database(sync_url)

    async_engine = create_async_engine(
        sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    )
    asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())


def test_fresh_database_migration_does_not_create_backup(tmp_path, monkeypatch):
    database = tmp_path / "fresh-no-backup.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setattr(
        database_schema,
        "_create_pre_migration_backup",
        lambda database_url: pytest.fail("fresh database must not be backed up"),
        raising=False,
    )

    database_schema.migrate_database(sync_url)

    current, head = database_schema.current_revision(sync_url)
    assert current == head


def test_migrate_database_on_existing_unversioned(tmp_path):
    """migrate 对旧版无版本管理的数据库执行 adopt。"""
    from app.maintenance.database_schema import migrate_database

    database = tmp_path / "legacy.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    migrate_database(sync_url)

    async_engine = create_async_engine(
        sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    )
    asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())


def test_migrate_database_on_already_head_is_noop(tmp_path):
    """migrate 对已在 head 的数据库是 no-op。"""
    from app.maintenance.database_schema import migrate_database

    database = tmp_path / "current.db"
    sync_url = f"sqlite:///{database.as_posix()}"

    # 先 upgrade 到 head
    command.upgrade(migration_config(sync_url), "head")
    # 再次 migrate 应该是 no-op（不抛异常）
    migrate_database(sync_url)

    async_engine = create_async_engine(
        sync_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    )
    asyncio.run(require_current_schema(async_engine))
    asyncio.run(async_engine.dispose())


def test_existing_versioned_database_is_backed_up_before_upgrade(tmp_path, monkeypatch):
    database = tmp_path / "old-version.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    command.upgrade(migration_config(sync_url), "20260710_02")
    events = []

    monkeypatch.setattr(
        database_schema,
        "_create_pre_migration_backup",
        lambda database_url: events.append(
            ("backup", database_schema.current_revision(database_url)[0])
        ),
        raising=False,
    )
    original_upgrade = database_schema.command.upgrade

    def tracked_upgrade(config, revision):
        events.append(("upgrade", database_schema.current_revision(sync_url)[0]))
        return original_upgrade(config, revision)

    monkeypatch.setattr(database_schema.command, "upgrade", tracked_upgrade)

    database_schema.migrate_database(sync_url)

    assert events[:2] == [
        ("backup", "20260710_02"),
        ("upgrade", "20260710_02"),
    ]
    current, head = database_schema.current_revision(sync_url)
    assert current == head


def test_backup_failure_prevents_schema_upgrade(tmp_path, monkeypatch):
    database = tmp_path / "backup-failure.db"
    sync_url = f"sqlite:///{database.as_posix()}"
    command.upgrade(migration_config(sync_url), "20260710_02")

    def fail_backup(database_url):
        raise RuntimeError("backup failed")

    monkeypatch.setattr(
        database_schema,
        "_create_pre_migration_backup",
        fail_backup,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="backup failed"):
        database_schema.migrate_database(sync_url)

    assert database_schema.current_revision(sync_url)[0] == "20260710_02"


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


def test_application_startup_contains_no_implicit_schema_ddl():
    source = (Path(__file__).parent / "app" / "database.py").read_text(
        encoding="utf-8"
    )

    assert "Base.metadata.create_all" not in source
    assert "ALTER TABLE" not in source
    assert "_ensure_sqlite_columns" not in source
    assert "require_current_schema" in source


def test_reply_assistant_migration_adds_settings_and_rules(tmp_path):
    database = tmp_path / "reply-assistant.db"
    url = f"sqlite:///{database.as_posix()}"
    command.upgrade(migration_config(url), "20260713_02")
    command.upgrade(migration_config(url), "head")

    engine = create_engine(url)
    inspector = inspect(engine)
    assert {"reply_assistant_settings", "reply_rules"} <= set(
        inspector.get_table_names()
    )
    assert {
        "id",
        "enabled",
        "ai_enabled",
        "api_base_url",
        "api_key",
        "model",
        "system_prompt",
    } <= {
        column["name"]
        for column in inspector.get_columns("reply_assistant_settings")
    }
    engine.dispose()
