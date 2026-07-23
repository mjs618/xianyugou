"""P3 安全调度器：周期性检查到期账号并触发订单同步。

对应 docs/superpowers/specs/2026-07-05-safe-order-lifecycle-sync-design.md 的「调度与恢复」章节。

设计要点：
- 默认每 60 秒 tick 一次，检查哪些账号到期需要同步。
- 只调度 auto_sync_enabled=True 且 status='online' 的账号；paused/invalid 不调度。
- 到期判定：last_sync_at 为空，或 now - last_sync_at >= auto_sync_interval_minutes。
- 单账号串行：sync_orders_for_account 内部的 asyncio.Lock 保证同账号不并发；不同账号可并发。
- 手动同步与自动调度共享同一把锁，互斥；调度遇到 SyncAlreadyRunningError 时跳过。
- 服务重启后不集中补跑错过任务，只延迟执行一次（首个 tick 检查到期即同步一次）。
- 网络超时/5xx 不立即重试，等待下一周期（由 order_service 的 failure_kind='unknown' 计数熔断处理）。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from ..database import AsyncSessionLocal
from ..models import XianyuAccount
from ..utils.helpers import now_utc
from .xianyu.order_service import SyncAlreadyRunningError, sync_orders_for_account

logger = logging.getLogger(__name__)

# tick 间隔（秒）。每 60 秒检查一次到期账号。
TICK_INTERVAL_SECONDS = 60

# 单次 tick 内最大并发同步账号数（信号量限制，避免多账号同时发起 MTOP 请求触发反欺诈）。
MAX_CONCURRENT_SYNC = 2


class SyncScheduler:
    """后台自动同步调度器。单例，随应用生命周期启停。"""

    def __init__(
        self,
        tick_interval: int = TICK_INTERVAL_SECONDS,
        max_concurrent: int = MAX_CONCURRENT_SYNC,
    ) -> None:
        self._tick_interval = tick_interval
        self._max_concurrent = max_concurrent
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """启动调度循环。已运行则忽略。"""
        if self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="sync-scheduler")

    async def stop(self) -> None:
        """停止调度循环，等待当前 tick 结束。"""
        if not self.running:
            return
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
        logger.info("同步调度器已启动，tick 间隔 %s 秒", self._tick_interval)
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception:
                # tick 内部异常不应终止调度循环
                logger.exception("调度 tick 发生未预期异常")
            # 等待下一个 tick 或停止信号
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._tick_interval
                )
            except asyncio.TimeoutError:
                pass  # 超时即到下一个 tick
        logger.info("同步调度器已停止")

    async def _tick(self) -> None:
        """单次 tick：查询到期账号并触发同步。"""
        due_accounts = await self.find_due_accounts()
        if not due_accounts:
            return
        logger.debug("发现 %d 个到期账号：%s", len(due_accounts), due_accounts)
        # 信号量限制并发账号数，避免多账号同时发起 MTOP 请求触发反欺诈
        sem = asyncio.Semaphore(self._max_concurrent)

        async def _bounded_sync(account_id: int) -> None:
            async with sem:
                await self._sync_one(account_id)

        await asyncio.gather(
            *(_bounded_sync(account_id) for account_id in due_accounts),
            return_exceptions=True,
        )

    async def find_due_accounts(self) -> list[int]:
        """返回到期需同步的账号 ID 列表。

        到期条件：auto_sync_enabled=True 且 status='online' 且
        (last_sync_at 为空 或 now - last_sync_at >= auto_sync_interval_minutes)。
        """
        now = now_utc()
        async with AsyncSessionLocal() as db:
            stmt = select(
                XianyuAccount.id,
                XianyuAccount.auto_sync_interval_minutes,
                XianyuAccount.last_sync_at,
            ).where(
                XianyuAccount.auto_sync_enabled.is_(True),
                XianyuAccount.status == "online",
                # P2-3 软删除：跳过已删除账号
                XianyuAccount.deleted_at.is_(None),
            )
            rows = (await db.execute(stmt)).all()

        due: list[int] = []
        for account_id, interval_minutes, last_sync_at in rows:
            if last_sync_at is None:
                due.append(account_id)
                continue
            elapsed = now - last_sync_at
            if elapsed >= timedelta(minutes=interval_minutes):
                due.append(account_id)
        return due

    async def _sync_one(self, account_id: int) -> None:
        """对单个账号执行同步。创建独立会话，提交或回滚。"""
        try:
            async with AsyncSessionLocal() as db:
                result = await sync_orders_for_account(db, account_id, max_pages=2)
                await db.commit()
            if result.get("success"):
                logger.info(
                    "账号 %s 自动同步成功：拉取 %s 单，新建 %s 单，跳过 %s 单",
                    account_id,
                    result.get("fetched"),
                    result.get("created_count"),
                    result.get("skipped_count"),
                )
            else:
                logger.warning(
                    "账号 %s 自动同步失败：%s", account_id, result.get("error")
                )
        except SyncAlreadyRunningError:
            # 手动同步正在进行，跳过本次自动调度
            logger.debug("账号 %s 正在同步中，跳过自动调度", account_id)
        except Exception:
            logger.exception("账号 %s 自动同步发生未预期异常", account_id)


# 模块级单例，随应用生命周期启停
scheduler = SyncScheduler()
