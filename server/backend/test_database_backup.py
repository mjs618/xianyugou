import json
import os
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
