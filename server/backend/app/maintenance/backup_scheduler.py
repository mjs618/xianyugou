"""P1-2 定时备份调度器：每日自动备份数据库，保留 14 天。

对应原计划文档「P1-2 定时备份调度」：
- 默认每 3600 秒（1 小时）tick 一次，检查是否需要备份
- 距上次成功备份 ≥ 86400 秒（24 小时）则触发备份
- 备份目标路径：data/backups/daily/xianyu-YYYYMMDD-HHMMSS.db
- 备份后清理过期文件（默认 14 天保留期）
- 通过扫目录最新文件 mtime 判断距上次备份时间，避免改表结构

设计参考 sync_scheduler.py 的 SyncScheduler 模式：
- 单例，随应用生命周期启停
- tick 内部异常不终止调度循环
- 服务重启后不集中补跑，只延迟执行一次
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import BACKEND_DIR, settings as app_settings
from .database_backup import cleanup_old_backups, create_backup, resolve_sqlite_path

logger = logging.getLogger(__name__)

# tick 间隔（秒）。每小时检查一次是否需要备份。
TICK_INTERVAL_SECONDS = 3600

# 备份间隔（秒）。距上次成功备份超过此值则触发。
BACKUP_INTERVAL_SECONDS = 86400  # 24 小时

# 备份保留期（天）。超过此天数的备份会被清理。
RETENTION_DAYS = 14

# 备份目录
BACKUP_DIR: Path = BACKEND_DIR / "data" / "backups" / "daily"


class BackupScheduler:
    """后台定时备份调度器。单例，随应用生命周期启停。"""

    def __init__(
        self,
        tick_interval: int = TICK_INTERVAL_SECONDS,
        backup_interval: int = BACKUP_INTERVAL_SECONDS,
        retention_days: int = RETENTION_DAYS,
        backup_dir: Path | None = None,
    ) -> None:
        self._tick_interval = tick_interval
        self._backup_interval = backup_interval
        self._retention_days = retention_days
        self._backup_dir = backup_dir if backup_dir is not None else BACKUP_DIR
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None  # 在 start() 中创建（需要 event loop）

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """启动调度循环。已运行则忽略。"""
        if self.running:
            return
        self._stop_event = asyncio.Event()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="backup-scheduler")

    async def stop(self) -> None:
        """停止调度循环，等待当前 tick 结束。"""
        if not self.running:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        logger.info(
            "备份调度器已启动，tick 间隔 %s 秒，备份间隔 %s 秒，保留 %s 天",
            self._tick_interval,
            self._backup_interval,
            self._retention_days,
        )
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception:
                # tick 内部异常不应终止调度循环
                logger.exception("备份 tick 发生未预期异常")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._tick_interval
                )
            except asyncio.TimeoutError:
                pass  # 超时即到下一个 tick
        logger.info("备份调度器已停止")

    async def _tick(self) -> None:
        """单次 tick：检查是否需要备份，需要则触发。"""
        last_backup_age = self._seconds_since_last_backup()
        if last_backup_age is not None and last_backup_age < self._backup_interval:
            logger.debug(
                "距上次备份 %s 秒，不足 %s 秒，跳过", last_backup_age, self._backup_interval
            )
            return
        await self._do_backup()

    async def _do_backup(self) -> None:
        """执行备份：调用 create_backup + cleanup_old_backups。"""
        try:
            source = resolve_sqlite_path(app_settings.database_url)
        except Exception as exc:
            logger.warning("无法解析数据库路径，跳过备份：%s", exc)
            return

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destination = self._backup_dir / f"xianyu-{timestamp}.db"

        # 文件名碰撞（同一秒内多次触发）则追加序号
        counter = 0
        while destination.exists():
            counter += 1
            destination = self._backup_dir / f"xianyu-{timestamp}-{counter}.db"

        try:
            # create_backup 是同步阻塞操作，放到线程池避免阻塞事件循环
            await asyncio.to_thread(create_backup, source, destination)
            logger.info("定时备份完成：%s", destination.name)
        except Exception as exc:
            logger.error("定时备份失败：%s", exc)
            return

        # 清理过期备份
        try:
            removed = await asyncio.to_thread(
                cleanup_old_backups, self._backup_dir, self._retention_days
            )
            if removed > 0:
                logger.info(
                    "已清理 %s 个过期备份（保留期 %s 天）",
                    removed,
                    self._retention_days,
                )
        except Exception as exc:
            logger.warning("清理过期备份失败：%s", exc)

    def _seconds_since_last_backup(self) -> float | None:
        """返回距上次备份的秒数；无备份记录返回 None。"""
        if not self._backup_dir.exists():
            return None
        db_files = [f for f in self._backup_dir.iterdir() if f.is_file() and f.suffix == ".db"]
        if not db_files:
            return None
        latest_mtime = max(f.stat().st_mtime for f in db_files)
        return time.time() - latest_mtime

    def _last_backup_at(self) -> datetime | None:
        """P1-3 监控指标：返回最近一次备份的 UTC 时间；无备份返回 None。"""
        if not self._backup_dir.exists():
            return None
        db_files = [f for f in self._backup_dir.iterdir() if f.is_file() and f.suffix == ".db"]
        if not db_files:
            return None
        latest_mtime = max(f.stat().st_mtime for f in db_files)
        return datetime.fromtimestamp(latest_mtime, timezone.utc)

    def _count_backups(self) -> int:
        """P1-3 监控指标：返回当前备份目录中的 .db 备份文件数量。"""
        if not self._backup_dir.exists():
            return 0
        return sum(1 for f in self._backup_dir.iterdir() if f.is_file() and f.suffix == ".db")


# 模块级单例，随应用生命周期启停
scheduler = BackupScheduler()
