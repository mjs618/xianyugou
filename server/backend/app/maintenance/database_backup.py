"""Create and verify consistent SQLite backups without exposing business data."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
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
        with closing(sqlite3.connect(source)) as source_connection:
            with closing(sqlite3.connect(temporary)) as backup_connection:
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
