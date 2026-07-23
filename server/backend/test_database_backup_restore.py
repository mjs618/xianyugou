"""E6 restore_backup 恢复流程测试。

覆盖：
- 成功恢复：备份文件 → 活跃数据库，数据被覆盖
- 恢复后自动生成 .pre_restore.bak（回退用）
- 恢复报告字段正确
- 校验失败的备份被拒绝（不改 target）
- 缺失 manifest 被拒绝
- 不存在的备份文件被拒绝
- 路径穿越防护（路由层，此处只测核心函数）

与 test_database_backup.py 互补：前者测 create/verify，此处测 restore。
"""
import json
import sqlite3
from pathlib import Path

import pytest

from app.maintenance.database_backup import (
    BackupError,
    create_backup,
    restore_backup,
)


def _create_source_database(path: Path) -> None:
    """创建一个含 2 张表 2 行数据的测试数据库。"""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE transactions (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO customers (name) VALUES ('测试客户')")
        connection.execute("INSERT INTO transactions (customer_id) VALUES (1)")
        connection.commit()


def _count_rows(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def test_restore_backup_success_overwrites_target(tmp_path: Path):
    """恢复成功：target 数据被备份内容覆盖。"""
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    # target 是一个不同的数据库（有不同的表结构和数据）
    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO other (id) VALUES (999)")
        conn.commit()

    report = restore_backup(backup_path, target)

    # target 现在应该有 source 的表结构和数据，other 表应消失
    assert _count_rows(target, "customers") == 1
    assert _count_rows(target, "transactions") == 1
    # other 表不应再存在
    with sqlite3.connect(target) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert tables == {"customers", "transactions"}
    assert report["integrity_check"] == "ok"
    assert report["table_counts"] == {"customers": 1, "transactions": 1}


def test_restore_backup_creates_pre_restore_backup(tmp_path: Path):
    """恢复后自动生成 .pre_restore.bak，包含恢复前的旧数据。"""
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE old_data (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO old_data (val) VALUES ('旧数据')")
        conn.commit()

    restore_backup(backup_path, target)

    pre_restore = target.with_name("target.pre_restore.bak")
    assert pre_restore.exists()
    # pre_restore 应包含恢复前的旧数据
    with sqlite3.connect(pre_restore) as conn:
        rows = conn.execute("SELECT val FROM old_data").fetchall()
    assert rows == [("旧数据",)]


def test_restore_backup_report_structure(tmp_path: Path):
    """恢复报告包含正确的字段。"""
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE placeholder (id INTEGER)")
        conn.commit()

    report = restore_backup(backup_path, target)

    assert "pre_restore_path" in report
    assert "integrity_check" in report
    assert "table_counts" in report
    assert report["integrity_check"] == "ok"
    assert isinstance(report["table_counts"], dict)


def test_restore_backup_rejects_corrupted_backup(tmp_path: Path):
    """校验失败的备份（被篡改）被拒绝，target 不受影响。"""
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    # 篡改备份文件
    with sqlite3.connect(backup_path) as conn:
        conn.execute("INSERT INTO customers (name) VALUES ('篡改')")
        conn.commit()

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE preserved (id INTEGER)")
        conn.commit()

    with pytest.raises(BackupError, match="checksum mismatch"):
        restore_backup(backup_path, target)

    # target 应保持不变
    with sqlite3.connect(target) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert "preserved" in tables
    assert "customers" not in tables


def test_restore_backup_rejects_missing_manifest(tmp_path: Path):
    """缺失 manifest 的备份被拒绝。"""
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    # 删除 manifest（路径与 create_backup 一致：backup.db → backup.manifest.json）
    manifest = backup_path.with_suffix(".manifest.json")
    manifest.unlink()

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE placeholder (id INTEGER)")
        conn.commit()

    with pytest.raises(BackupError, match="manifest not found"):
        restore_backup(backup_path, target)


def test_restore_backup_rejects_nonexistent_backup(tmp_path: Path):
    """不存在的备份文件被拒绝。"""
    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE placeholder (id INTEGER)")
        conn.commit()

    with pytest.raises(BackupError, match="does not exist"):
        restore_backup(tmp_path / "nonexistent.db", target)


def test_restore_backup_restores_empty_database(tmp_path: Path):
    """恢复一个空备份（只有表结构无数据）。"""
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE empty_table (id INTEGER PRIMARY KEY)")
        conn.commit()

    backup_path = tmp_path / "backup.db"
    create_backup(source, backup_path)

    target = tmp_path / "target.db"
    with sqlite3.connect(target) as conn:
        conn.execute("CREATE TABLE old (id INTEGER)")
        conn.execute("INSERT INTO old (id) VALUES (1)")
        conn.commit()

    report = restore_backup(backup_path, target)

    assert report["table_counts"] == {"empty_table": 0}
    assert _count_rows(target, "empty_table") == 0
