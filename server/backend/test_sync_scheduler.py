import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import XianyuAccount
from app.services.sync_scheduler import SyncScheduler
from app.utils.helpers import now_utc


class SyncSchedulerDueTests(unittest.IsolatedAsyncioTestCase):
    """测试到期账号判定逻辑。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _create_account(self, **kwargs) -> XianyuAccount:
        defaults = dict(
            nickname="test-account",
            unb="12345",
            cookies="encrypted",
            status="online",
        )
        defaults.update(kwargs)
        async with self.Session() as db:
            account = XianyuAccount(**defaults)
            db.add(account)
            await db.commit()
            await db.refresh(account)
            return account

    async def test_finds_account_with_no_prior_sync(self):
        """从未同步过的账号立即到期。"""
        account = await self._create_account(auto_sync_enabled=True)
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [account.id])

    async def test_skips_account_within_interval(self):
        """上次同步时间未超过间隔的账号不到期。"""
        account = await self._create_account(
            auto_sync_enabled=True,
            auto_sync_interval_minutes=120,
            last_sync_at=now_utc() - timedelta(minutes=30),
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [])

    async def test_finds_account_past_interval(self):
        """上次同步时间超过间隔的账号到期。"""
        account = await self._create_account(
            auto_sync_enabled=True,
            auto_sync_interval_minutes=60,
            last_sync_at=now_utc() - timedelta(minutes=90),
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [account.id])

    async def test_skips_disabled_auto_sync(self):
        """auto_sync_enabled=False 的账号不被调度。"""
        await self._create_account(
            auto_sync_enabled=False,
            auto_sync_interval_minutes=60,
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [])

    async def test_skips_paused_account(self):
        """paused 状态的账号不被调度（需人工恢复）。"""
        await self._create_account(
            auto_sync_enabled=True,
            status="paused",
            paused_at=now_utc(),
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [])

    async def test_skips_invalid_account(self):
        """invalid 状态的账号不被调度。"""
        await self._create_account(
            auto_sync_enabled=True,
            status="invalid",
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [])

    async def test_respects_per_account_interval(self):
        """不同账号的间隔独立判定。"""
        short = await self._create_account(
            nickname="short",
            auto_sync_enabled=True,
            auto_sync_interval_minutes=60,
            last_sync_at=now_utc() - timedelta(minutes=70),
        )
        long_account = await self._create_account(
            nickname="long",
            auto_sync_enabled=True,
            auto_sync_interval_minutes=240,
            last_sync_at=now_utc() - timedelta(minutes=70),
        )
        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()
        self.assertEqual(due, [short.id])


class SyncSchedulerSyncOneTests(unittest.IsolatedAsyncioTestCase):
    """测试单账号同步执行与异常处理。"""

    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_sync_one_invokes_sync_with_limited_pages(self):
        """自动调度调用 sync_orders_for_account 并限制 max_pages=2（最近两页）。"""
        scheduler = SyncScheduler()
        fake_result = {"success": True, "fetched": 3, "created_count": 1, "skipped_count": 2}
        with (
            patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session),
            patch(
                "app.services.sync_scheduler.sync_orders_for_account",
                new=AsyncMock(return_value=fake_result),
            ) as mock_sync,
        ):
            await scheduler._sync_one(42)

        mock_sync.assert_awaited_once()
        # 自动调度限制为最近两页（设计文档：普通同步最多读取最近两页）
        self.assertEqual(mock_sync.call_args.kwargs.get("max_pages"), 2)
        # 第一个位置参数是 account_id
        self.assertEqual(mock_sync.call_args.args[1], 42)

    async def test_sync_one_skips_when_already_running(self):
        """SyncAlreadyRunningError 不应上抛，静默跳过。"""
        from app.services.xianyu.order_service import SyncAlreadyRunningError

        scheduler = SyncScheduler()
        with (
            patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session),
            patch(
                "app.services.sync_scheduler.sync_orders_for_account",
                new=AsyncMock(side_effect=SyncAlreadyRunningError("busy")),
            ),
        ):
            # 不应抛异常
            await scheduler._sync_one(999)

    async def test_sync_one_swallows_unexpected_exception(self):
        """未知异常不应上抛，避免影响其他账号的 gather。"""
        scheduler = SyncScheduler()
        with (
            patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session),
            patch(
                "app.services.sync_scheduler.sync_orders_for_account",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            await scheduler._sync_one(999)


class SyncSchedulerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    """测试调度器启停生命周期。"""

    async def test_start_stop_idempotent(self):
        """重复 start/stop 不报错。"""
        scheduler = SyncScheduler(tick_interval=3600)
        self.assertFalse(scheduler.running)
        scheduler.start()
        self.assertTrue(scheduler.running)
        scheduler.start()  # 重复 start 忽略
        self.assertTrue(scheduler.running)
        await scheduler.stop()
        self.assertFalse(scheduler.running)
        await scheduler.stop()  # 重复 stop 忽略

    async def test_tick_with_no_due_accounts_is_noop(self):
        """无到期账号时 tick 不执行同步。"""
        scheduler = SyncScheduler()
        with (
            patch.object(
                scheduler, "find_due_accounts", new=AsyncMock(return_value=[])
            ),
            patch(
                "app.services.sync_scheduler.sync_orders_for_account",
                new=AsyncMock(),
            ) as mock_sync,
        ):
            await scheduler._tick()
            mock_sync.assert_not_awaited()

    async def test_tick_syncs_all_due_accounts(self):
        """有到期账号时 tick 对每个账号触发同步。"""
        scheduler = SyncScheduler()
        with (
            patch.object(
                scheduler,
                "find_due_accounts",
                new=AsyncMock(return_value=[1, 2, 3]),
            ),
            patch.object(
                scheduler, "_sync_one", new=AsyncMock()
            ) as mock_sync_one,
        ):
            await scheduler._tick()
            self.assertEqual(mock_sync_one.await_count, 3)
            awaited_ids = {call.args[0] for call in mock_sync_one.await_args_list}
            self.assertEqual(awaited_ids, {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
