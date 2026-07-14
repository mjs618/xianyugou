"""P2-3 修复验证：账号软删除（deleted_at）。

测试覆盖：
1. delete_account 设置 deleted_at + status=disabled（不物理删除）
2. list_accounts 不返回已删除账号
3. get_account 仍能查到已删除账号（保留关联数据可追溯）
4. delete_account 幂等：再次删除不报错
5. ensure_manual_order_sync_allowed 拒绝已删除账号
6. update_account 拒绝修改已删除账号
7. test_account 拒绝测试已删除账号
8. recover_account 拒绝恢复已删除账号
9. sync_scheduler.find_due_accounts 跳过已删除账号
"""
import unittest
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import XianyuAccount
from app.services.sync_scheduler import SyncScheduler
from app.services.xianyu.account_service import (
    XianyuAccountError,
    delete_account,
    ensure_manual_order_sync_allowed,
    get_account,
    list_accounts,
    recover_account,
    update_account,
)
# test_account 是服务函数（校验 Cookie），用别名避免 pytest 收集为测试
from app.services.xianyu.account_service import test_account as check_account_cookies
from app.utils.helpers import now_utc


class AccountSoftDeleteTests(unittest.IsolatedAsyncioTestCase):
    """P2-3：账号软删除。"""

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

    async def test_delete_account_sets_deleted_at_and_disabled_status(self):
        """delete_account 设置 deleted_at + status=disabled。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        # 账号仍存在（未被物理删除），但 deleted_at 非空
        async with self.Session() as db:
            deleted = await get_account(db, account.id)
        self.assertIsNotNone(deleted)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.status, "disabled")

    async def test_list_accounts_excludes_deleted(self):
        """list_accounts 不返回已删除账号。"""
        active = await self._create_account(nickname="active", unb="10001")
        deleted = await self._create_account(nickname="deleted", unb="10002")

        async with self.Session() as db:
            await delete_account(db, deleted.id)
            await db.commit()

        async with self.Session() as db:
            accounts = await list_accounts(db)

        account_ids = [a.id for a in accounts]
        self.assertIn(active.id, account_ids)
        self.assertNotIn(deleted.id, account_ids)

    async def test_get_account_still_finds_deleted(self):
        """get_account 仍能查到已删除账号（历史数据可追溯）。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        async with self.Session() as db:
            found = await get_account(db, account.id)
        self.assertIsNotNone(found)
        self.assertIsNotNone(found.deleted_at)

    async def test_delete_account_is_idempotent(self):
        """重复删除已删除账号不报错。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        # 第二次删除不报错
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

    async def test_ensure_manual_sync_rejects_deleted_account(self):
        """ensure_manual_order_sync_allowed 拒绝已删除账号。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await ensure_manual_order_sync_allowed(db, account.id)
        self.assertIn("已删除", str(ctx.exception))

    async def test_update_account_rejects_deleted(self):
        """update_account 拒绝修改已删除账号。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await update_account(db, account.id, {"nickname": "new-name"})
        self.assertIn("已删除", str(ctx.exception))

    async def test_test_account_rejects_deleted(self):
        """test_account 拒绝测试已删除账号。"""
        account = await self._create_account()
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await check_account_cookies(db, account.id)
        self.assertIn("已删除", str(ctx.exception))

    async def test_recover_account_rejects_deleted(self):
        """recover_account 拒绝恢复已删除账号。"""
        account = await self._create_account(status="paused", paused_at=now_utc())
        async with self.Session() as db:
            await delete_account(db, account.id)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, account.id)
        self.assertIn("已删除", str(ctx.exception))

    async def test_scheduler_skips_deleted_account(self):
        """sync_scheduler.find_due_accounts 跳过已删除账号。"""
        # 创建一个到期账号
        active = await self._create_account(
            nickname="active",
            unb="80001",
            auto_sync_enabled=True,
            auto_sync_interval_minutes=60,
        )
        # 创建一个已删除的到期账号
        deleted = await self._create_account(
            nickname="deleted",
            unb="80002",
            auto_sync_enabled=True,
            auto_sync_interval_minutes=60,
        )
        async with self.Session() as db:
            await delete_account(db, deleted.id)
            await db.commit()

        scheduler = SyncScheduler()
        with patch("app.services.sync_scheduler.AsyncSessionLocal", self.Session):
            due = await scheduler.find_due_accounts()

        self.assertIn(active.id, due)
        self.assertNotIn(deleted.id, due)


if __name__ == "__main__":
    unittest.main()
