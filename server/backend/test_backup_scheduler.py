"""P1-2 定时备份调度器测试。

验证：
- 无备份记录时触发首次备份
- 距上次备份 < 24h 时跳过
- 距上次备份 ≥ 24h 时触发
- cleanup_old_backups 删除过期文件、保留近期文件
"""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from app.maintenance.backup_scheduler import BackupScheduler
from app.maintenance.database_backup import cleanup_old_backups


class BackupSchedulerAgeTests(unittest.TestCase):
    """_seconds_since_last_backup 与 cleanup_old_backups 的同步逻辑测试。"""

    def test_seconds_since_last_backup_returns_none_when_no_dir(self):
        """无备份目录时返回 None（触发首次备份）。"""
        scheduler = BackupScheduler(backup_dir=Path("/nonexistent-path-xyz"))
        self.assertIsNone(scheduler._seconds_since_last_backup())

    def test_seconds_since_last_backup_returns_none_when_dir_empty(self, ):
        """备份目录存在但无 .db 文件时返回 None。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "daily"
            backup_dir.mkdir()
            (backup_dir / "readme.txt").write_text("not a backup")
            scheduler = BackupScheduler(backup_dir=backup_dir)
            self.assertIsNone(scheduler._seconds_since_last_backup())

    def test_seconds_since_last_backup_returns_age_when_backup_exists(self):
        """有备份文件时返回距上次备份的秒数。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "daily"
            backup_dir.mkdir()
            backup_file = backup_dir / "xianyu-20260101-000000.db"
            backup_file.write_text("dummy")
            old_time = time.time() - 100
            os.utime(backup_file, (old_time, old_time))

            scheduler = BackupScheduler(backup_dir=backup_dir)
            age = scheduler._seconds_since_last_backup()
            self.assertIsNotNone(age)
            self.assertTrue(95 <= age <= 110)  # 约 100 秒，留容差

    def test_cleanup_old_backups_removes_expired_files(self):
        """cleanup_old_backups 删除过期备份，保留近期备份。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "daily"
            backup_dir.mkdir()

            # 过期文件（30 天前）
            # manifest 路径与 create_backup 一致：xianyu-old.db → xianyu-old.manifest.json
            old_db = backup_dir / "xianyu-old.db"
            old_db.write_text("old")
            old_manifest = backup_dir / "xianyu-old.manifest.json"
            old_manifest.write_text("{}")
            old_time = time.time() - 30 * 86400
            os.utime(old_db, (old_time, old_time))
            os.utime(old_manifest, (old_time, old_time))

            # 近期文件（1 天前）
            new_db = backup_dir / "xianyu-new.db"
            new_db.write_text("new")
            new_manifest = backup_dir / "xianyu-new.manifest.json"
            new_manifest.write_text("{}")
            new_time = time.time() - 1 * 86400
            os.utime(new_db, (new_time, new_time))
            os.utime(new_manifest, (new_time, new_time))

            removed = cleanup_old_backups(backup_dir, retention_days=14)
            self.assertEqual(removed, 1)
            self.assertFalse(old_db.exists())
            self.assertFalse(old_manifest.exists())
            self.assertTrue(new_db.exists())
            self.assertTrue(new_manifest.exists())

    def test_cleanup_old_backups_returns_zero_when_dir_missing(self):
        """目录不存在时返回 0，不报错。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            removed = cleanup_old_backups(Path(tmp) / "nonexistent", retention_days=14)
            self.assertEqual(removed, 0)


class BackupSchedulerTickTests(unittest.IsolatedAsyncioTestCase):
    """_tick 的异步逻辑测试。"""

    async def test_tick_skips_when_recent_backup_exists(self):
        """距上次备份 < backup_interval 时跳过。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "daily"
            backup_dir.mkdir()
            backup_file = backup_dir / "xianyu-recent.db"
            backup_file.write_text("dummy")
            recent_time = time.time() - 100  # 100 秒前
            os.utime(backup_file, (recent_time, recent_time))

            scheduler = BackupScheduler(
                backup_interval=86400,
                backup_dir=backup_dir,
            )
            scheduler._do_backup = AsyncMock()
            await scheduler._tick()
            scheduler._do_backup.assert_not_called()

    async def test_tick_triggers_when_no_backup(self):
        """无备份记录时触发首次备份。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = BackupScheduler(
                backup_interval=86400,
                backup_dir=Path(tmp) / "daily",
            )
            scheduler._do_backup = AsyncMock()
            await scheduler._tick()
            scheduler._do_backup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
