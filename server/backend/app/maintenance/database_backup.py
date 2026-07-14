"""Create and verify consistent SQLite backups without exposing business data."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.config import settings


class BackupError(RuntimeError):
    """Raised when a backup cannot be created or verified safely."""


# 表名白名单：只允许字母/数字/下划线（防双引号注入与特殊字符）
# 表名来自 sqlite_master 系统表查询，本身不是用户输入，但白名单提供纵深防御
_TABLE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


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
    """读取数据库的 integrity_check 与各表行数。

    表名通过白名单正则验证后才用于 SQL（纵深防御，避免特殊字符破坏 SQL）。
    """
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        counts: dict[str, int] = {}
        for (name,) in rows:
            name_str = str(name)
            if not _TABLE_NAME_RE.match(name_str):
                # 跳过不符合命名规范的表（理论不应出现，防御性处理）
                raise BackupError(f"unexpected table name from sqlite_master: {name_str!r}")
            counts[name_str] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{name_str}"').fetchone()[0]
            )
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


# 恢复时与目标 db 一起备份/清理的 WAL 辅助文件后缀
_WAL_SIDE_SUFFIXES = ("-wal", "-shm")


def restore_backup(backup_path: Path, target_path: Path) -> dict[str, Any]:
    """从备份文件恢复数据库（在线，用 SQLite backup API，无需停服）。

    流程：
    1. 校验备份 manifest（sha256 + 表数 + integrity_check）
    2. 备份当前 target 到 ``target.pre_restore.bak``（含 WAL/SHM），失败可回退
    3. 用 SQLite backup API 在线复制 backup → target（覆盖现有数据）
    4. 删除恢复后遗留的 WAL/SHM（backup 后是干净状态）
    5. 返回恢复报告（pre_restore 路径 + integrity + table_counts）

    异常时回退：把 .pre_restore.bak 复制回 target，再抛出原始异常。

    注意：调用方应确保恢复期间无并发写请求（单用户应用天然满足）。
    """
    backup_path = backup_path.resolve()
    target_path = target_path.resolve()
    if not backup_path.is_file():
        raise BackupError("backup file does not exist")
    # manifest 路径与 create_backup 保持一致：backup.db → backup.manifest.json
    # （with_suffix(".manifest.json") 会替换 .db 后缀）
    manifest_path = backup_path.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise BackupError("backup manifest not found, cannot verify")

    # 1. 校验备份（失败则直接抛错，不动 target）
    verify_backup(backup_path, manifest_path)

    # 2. 备份当前 target（回退用）
    # 路径：target.db → target.pre_restore.bak（替换 .db 后缀）
    pre_restore = target_path.with_suffix(".pre_restore.bak")
    if target_path.exists():
        shutil.copy2(target_path, pre_restore)
        for suffix in _WAL_SIDE_SUFFIXES:
            side = target_path.with_name(target_path.name + suffix)
            if side.exists():
                shutil.copy2(side, pre_restore.with_name(pre_restore.name + suffix))

    # 3. 在线复制 backup → target（SQLite backup API 正确处理 WAL 和锁）
    try:
        # 源：只读打开备份文件；目标：读写打开活跃数据库（busy_timeout 容忍并发读）
        with closing(sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro", uri=True)) as src:
            with closing(
                sqlite3.connect(
                    target_path.as_posix(),
                    timeout=10,
                )
            ) as dst:
                src.backup(dst)
        # 4. 删除 backup 后遗留的 WAL/SHM（backup API 写入后是干净状态）
        for suffix in _WAL_SIDE_SUFFIXES:
            side = target_path.with_name(target_path.name + suffix)
            side.unlink(missing_ok=True)
    except Exception:
        # 回退：把 pre_restore 复制回 target
        if pre_restore.exists():
            shutil.copy2(pre_restore, target_path)
            for suffix in _WAL_SIDE_SUFFIXES:
                side = pre_restore.with_name(pre_restore.name + suffix)
                if side.exists():
                    shutil.copy2(side, target_path.with_name(target_path.name + suffix))
        raise

    # 5. 返回恢复报告
    integrity, counts = _inspect(target_path)
    return {
        "pre_restore_path": str(pre_restore),
        "integrity_check": integrity,
        "table_counts": counts,
    }


def cleanup_old_backups(backup_dir: Path, retention_days: int = 14) -> int:
    """删除超过保留期的备份文件（.db 与对应 .manifest.json），返回删除的备份对数。"""
    import time

    cutoff = time.time() - retention_days * 86400
    if not backup_dir.exists():
        return 0
    removed = 0
    for f in backup_dir.iterdir():
        if not f.is_file() or f.suffix != ".db":
            continue
        if f.stat().st_mtime >= cutoff:
            continue
        f.unlink(missing_ok=True)
        # 与 create_backup 一致：backup.db → backup.manifest.json
        manifest = f.with_suffix(".manifest.json")
        manifest.unlink(missing_ok=True)
        removed += 1
    return removed


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
    raise SystemExit(main())
