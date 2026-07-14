"""E9 测试：sync_orders_for_account TOCTOU 竞态修复。

验证：
1. 同步过程中第二次调用 sync_orders_for_account 抛 SyncAlreadyRunningError
   （不是默默等待，而是立即拒绝）
2. 异常情况下 _syncing_accounts 仍被清理（finally 块）
3. 同步完成后 _syncing_accounts 被清理
"""
import asyncio
import unittest
from unittest.mock import patch, AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import XianyuAccount
from app.services.xianyu import order_service
from app.services.xianyu.order_service import (
    SyncAlreadyRunningError,
    _syncing_accounts,
    sync_orders_for_account,
)


class SyncLockToctouTests(unittest.IsolatedAsyncioTestCase):
    """sync_orders_for_account TOCTOU 修复验证。"""

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
        # 每个测试开始前清理全局状态
        _syncing_accounts.clear()

    async def asyncTearDown(self):
        _syncing_accounts.clear()
        await self.engine.dispose()

    async def _create_account(self, db, *, account_id: int = 1, status: str = "online") -> XianyuAccount:
        account = XianyuAccount(
            id=account_id,
            nickname="测试账号",
            unb="123456",
            cookies="unb=123456; _m_h5_tk=abc_token_1700000000000",
            status=status,
        )
        db.add(account)
        await db.commit()
        return account

    async def test_second_concurrent_call_raises_immediately(self):
        """第二次调用在第一次未完成时应立即抛 SyncAlreadyRunningError。

        模拟：第一次调用阻塞在 event 上，第二次调用应立即被拒绝。
        """
        async with self.Session() as db:
            await self._create_account(db, account_id=1)

        # 用 event 控制第一次同步阻塞
        block_event = asyncio.Event()
        call_count = {"value": 0}

        async def slow_sync(db, account_id, *, max_pages=10):
            call_count["value"] += 1
            await block_event.wait()  # 阻塞直到测试主动释放
            return {"synced": 1}

        with patch.object(order_service, "_sync_orders_for_account_unlocked", side_effect=slow_sync):
            # 启动第一次同步（在后台 task 中运行）
            task1 = asyncio.create_task(self._run_sync(1, max_pages=2))
            # 等待第一次同步进入阻塞（set 中应该有 account_id=1）
            await asyncio.sleep(0.05)

            # 第二次调用应立即抛 SyncAlreadyRunningError
            async with self.Session() as db:
                with self.assertRaises(SyncAlreadyRunningError):
                    await sync_orders_for_account(db, 1, max_pages=2)

            # 释放阻塞，让第一次完成
            block_event.set()
            result = await task1
            self.assertEqual(result["synced"], 1)

        # 第一次只调用一次，第二次根本没进入
        self.assertEqual(call_count["value"], 1)

    async def test_syncing_accounts_cleared_after_success(self):
        """同步成功后 _syncing_accounts 被清理。"""
        async with self.Session() as db:
            await self._create_account(db, account_id=1)

        async def quick_sync(db, account_id, *, max_pages=10):
            return {"synced": 5}

        with patch.object(order_service, "_sync_orders_for_account_unlocked", side_effect=quick_sync):
            async with self.Session() as db:
                await sync_orders_for_account(db, 1, max_pages=2)

        self.assertNotIn(1, _syncing_accounts, "成功后应清理 set")

    async def test_syncing_accounts_cleared_after_exception(self):
        """同步抛异常时 _syncing_accounts 仍被清理（finally 块）。"""
        async with self.Session() as db:
            await self._create_account(db, account_id=1)

        async def failing_sync(db, account_id, *, max_pages=10):
            raise RuntimeError("同步失败")

        with patch.object(order_service, "_sync_orders_for_account_unlocked", side_effect=failing_sync):
            async with self.Session() as db:
                with self.assertRaises(RuntimeError):
                    await sync_orders_for_account(db, 1, max_pages=2)

        self.assertNotIn(1, _syncing_accounts, "异常后也应清理 set")

    async def test_syncing_accounts_cleared_after_sync_already_running(self):
        """SyncAlreadyRunningError 自身被抛时也不应污染 set。

        场景：A 调用同步（占用 set）→ B 调用被拒（不应添加 B 的 account_id 进 set，
        虽然是同一账号，但验证 finally 行为不影响其他场景）。
        """
        async with self.Session() as db:
            await self._create_account(db, account_id=1)

        block_event = asyncio.Event()

        async def slow_sync(db, account_id, *, max_pages=10):
            await block_event.wait()
            return {"synced": 1}

        with patch.object(order_service, "_sync_orders_for_account_unlocked", side_effect=slow_sync):
            task1 = asyncio.create_task(self._run_sync(1, max_pages=2))
            await asyncio.sleep(0.05)

            # 第二次被拒
            async with self.Session() as db:
                with self.assertRaises(SyncAlreadyRunningError):
                    await sync_orders_for_account(db, 1, max_pages=2)

            # 释放并等待完成
            block_event.set()
            await task1

        # 第一次完成后 set 应为空
        self.assertNotIn(1, _syncing_accounts)

    async def test_different_accounts_sync_concurrently(self):
        """不同账号可以并发同步（set 只拒绝相同 account_id）。"""
        async with self.Session() as db:
            await self._create_account(db, account_id=1)
            await self._create_account(db, account_id=2)

        block_event = asyncio.Event()
        sync_log = []

        async def slow_sync(db, account_id, *, max_pages=10):
            sync_log.append(f"start_{account_id}")
            await block_event.wait()
            sync_log.append(f"end_{account_id}")
            return {"synced": 1, "account_id": account_id}

        with patch.object(order_service, "_sync_orders_for_account_unlocked", side_effect=slow_sync):
            # 两个账号并发同步
            task1 = asyncio.create_task(self._run_sync(1, max_pages=2))
            task2 = asyncio.create_task(self._run_sync(2, max_pages=2))
            await asyncio.sleep(0.05)

            # 两个都进入了同步
            self.assertIn(1, _syncing_accounts)
            self.assertIn(2, _syncing_accounts)

            # 释放
            block_event.set()
            r1, r2 = await asyncio.gather(task1, task2)

        self.assertEqual(r1["account_id"], 1)
        self.assertEqual(r2["account_id"], 2)

    async def _run_sync(self, account_id: int, *, max_pages: int = 2):
        """辅助：在独立 Session 中执行同步。"""
        async with self.Session() as db:
            return await sync_orders_for_account(db, account_id, max_pages=max_pages)


if __name__ == "__main__":
    unittest.main()
