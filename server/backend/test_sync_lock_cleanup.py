"""P2-2 修复验证：账号删除时清理 _sync_locks 字典。

测试覆盖：
1. release_sync_lock 移除 _sync_locks 中的条目
2. release_sync_lock 对不存在的 key 幂等（不报错）
3. delete_account 后 _sync_locks 中不再保留该账号的锁
"""
import unittest
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import XianyuAccount
from app.services.xianyu.account_service import delete_account
from app.services.xianyu.order_service import (
    _sync_locks,
    _get_sync_lock,
    release_sync_lock,
)


class SyncLockCleanupTests(unittest.IsolatedAsyncioTestCase):
    """P2-2：_sync_locks 字典清理。"""

    async def asyncSetUp(self):
        # 清理可能残留的锁条目
        _sync_locks.clear()
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
        _sync_locks.clear()
        await self.engine.dispose()

    async def test_release_sync_lock_removes_entry(self):
        """release_sync_lock 移除 _sync_locks 中的条目。"""
        # 准备：制造一个 lock 条目
        lock = _get_sync_lock(99999)
        self.assertIn(99999, _sync_locks)
        self.assertIs(_sync_locks[99999], lock)
        # 执行
        release_sync_lock(99999)
        # 断言
        self.assertNotIn(99999, _sync_locks)

    async def test_release_sync_lock_idempotent(self):
        """不存在的 key 清理不应报错。"""
        # 多次清理不存在的 key
        release_sync_lock(88888)
        release_sync_lock(88888)
        # 无异常即通过
        self.assertNotIn(88888, _sync_locks)

    async def test_delete_account_cleans_up_sync_lock(self):
        """delete_account 后 _sync_locks 不再保留该账号的锁。"""
        # 准备：创建账号并获取锁
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="lock-test",
                unb="70001",
                cookies="encrypted",
                status="online",
            )
            db.add(account)
            await db.commit()
            await db.refresh(account)
            account_id = account.id

        # 制造锁条目
        _get_sync_lock(account_id)
        self.assertIn(account_id, _sync_locks)

        # 执行：删除账号
        async with self.Session() as db:
            await delete_account(db, account_id)
            await db.commit()

        # 断言：锁已被清理
        self.assertNotIn(account_id, _sync_locks)

    async def test_release_sync_lock_does_not_affect_other_accounts(self):
        """清理一个账号的锁不影响其他账号的锁。"""
        lock_a = _get_sync_lock(11111)
        lock_b = _get_sync_lock(22222)
        self.assertIn(11111, _sync_locks)
        self.assertIn(22222, _sync_locks)

        release_sync_lock(11111)
        self.assertNotIn(11111, _sync_locks)
        self.assertIn(22222, _sync_locks)
        self.assertIs(_sync_locks[22222], lock_b)


if __name__ == "__main__":
    unittest.main()
