"""D7 测试补充：recover_account 成功路径与所有拒绝路径。

验证账号熔断恢复的完整流程（设计文档 P3）：
1. 成功路径：status=paused + updated_at > paused_at + Cookie 校验通过
   → status=online, paused_at=None, consecutive_failures=0, last_error=None
   → 触发 account_recovered 通知（type=account_recovered）
2. 拒绝路径：账号不存在
3. 拒绝路径：已软删除账号
4. 拒绝路径：status != "paused"
5. 拒绝路径：updated_at <= paused_at（Cookie 未在暂停后更新）
6. 拒绝路径：Cookie 校验失败（缺 unb / _m_h5_tk）

测试用固定 AESGCM 密钥（mock _get_aesgcm）避免文件系统依赖。
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import NotificationRecord, XianyuAccount
from app.services.xianyu.account_service import (
    XianyuAccountError,
    recover_account,
)
from app.utils import crypto
from app.utils.crypto import encrypt_field


# 测试用固定密钥，避免依赖文件系统
TEST_KEY = b"\x02" * 32
TEST_AESGCM = AESGCM(TEST_KEY)

# 合法 Cookie：包含 unb + _m_h5_tk（带下划线分隔的 token_timestamp）
VALID_COOKIE = "unb=123456; _m_h5_tk=abc_token_1700000000000"
# 缺 _m_h5_tk 的 Cookie
COOKIE_MISSING_TOKEN = "unb=123456"
# 缺 unb 的 Cookie
COOKIE_MISSING_UNB = "_m_h5_tk=abc_token_1700000000000"


class RecoverAccountTests(unittest.IsolatedAsyncioTestCase):
    """recover_account 成功路径与拒绝路径。"""

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
        # mock AESGCM，避免 _load_or_create_key 触碰文件系统
        self._patcher = patch.object(crypto, "_get_aesgcm", return_value=TEST_AESGCM)
        self._patcher.start()

    async def asyncTearDown(self):
        self._patcher.stop()
        await self.engine.dispose()

    async def _create_paused_account(
        self,
        db,
        *,
        account_id: int = 1,
        cookie: str = VALID_COOKIE,
        paused_at: datetime | None = None,
        updated_at: datetime | None = None,
        consecutive_failures: int = 3,
        last_error: str = "认证失败",
    ) -> XianyuAccount:
        """创建已熔断的账号：status=paused + 已加密 cookies。"""
        if paused_at is None:
            paused_at = datetime(2026, 7, 1, 10, 0, 0)
        # updated_at 默认晚于 paused_at（满足「Cookie 已更新」前置条件）
        if updated_at is None:
            updated_at = paused_at + timedelta(hours=1)
        account = XianyuAccount(
            id=account_id,
            nickname="测试账号",
            unb="123456",
            cookies=encrypt_field(cookie),
            status="paused",
            last_error=last_error,
            auto_sync_enabled=False,
            auto_sync_interval_minutes=120,
            consecutive_failures=consecutive_failures,
            paused_at=paused_at,
            updated_at=updated_at,
        )
        db.add(account)
        await db.commit()
        return account

    # ==================== 成功路径 ====================

    async def test_recover_success_clears_paused_state(self):
        """成功恢复：清零失败计数、解除暂停、清 last_error。"""
        async with self.Session() as db:
            paused_at = datetime(2026, 7, 1, 10, 0, 0)
            await self._create_paused_account(
                db, account_id=1, paused_at=paused_at,
                updated_at=paused_at + timedelta(hours=2),
                consecutive_failures=5, last_error="认证失败",
            )

        async with self.Session() as db:
            account = await recover_account(db, 1)
            await db.commit()

            self.assertEqual(account.status, "online")
            self.assertIsNone(account.paused_at)
            self.assertEqual(account.consecutive_failures, 0)
            self.assertIsNone(account.last_error)
            # updated_at 被刷新
            self.assertGreater(account.updated_at, paused_at)

    async def test_recover_success_creates_recovered_notification(self):
        """成功恢复：触发 account_recovered 通知。"""
        async with self.Session() as db:
            await self._create_paused_account(db, account_id=1)

        async with self.Session() as db:
            await recover_account(db, 1)
            await db.commit()

        async with self.Session() as db:
            notifications = list(
                (await db.execute(
                    select(NotificationRecord).where(
                        NotificationRecord.type == "account_recovered",
                        NotificationRecord.ref_id == 1,
                    )
                )).scalars().all()
            )
            self.assertEqual(len(notifications), 1, "应创建一条 account_recovered 通知")
            n = notifications[0]
            self.assertEqual(n.status, "unread")
            self.assertIn("测试账号", n.content)

    async def test_recover_success_keeps_encrypted_cookies_unchanged(self):
        """成功恢复：cookies 字段本身不重新加密（仅校验时解密）。"""
        async with self.Session() as db:
            await self._create_paused_account(db, account_id=1)
            # 记录原 cookies 密文
            original_cookies = (await db.get(XianyuAccount, 1)).cookies

        async with self.Session() as db:
            await recover_account(db, 1)
            await db.commit()

        async with self.Session() as db:
            account = await db.get(XianyuAccount, 1)
            self.assertEqual(account.cookies, original_cookies, "cookies 密文不应被改写")

    async def test_recover_success_idempotent_on_same_day_notification(self):
        """同账号同天再次恢复：通知去重，不重复创建。"""
        async with self.Session() as db:
            await self._create_paused_account(db, account_id=1)

        # 第一次恢复
        async with self.Session() as db:
            await recover_account(db, 1)
            await db.commit()
        # 再次进入 paused
        async with self.Session() as db:
            account = await db.get(XianyuAccount, 1)
            account.status = "paused"
            account.paused_at = datetime(2026, 7, 1, 12, 0, 0)
            account.updated_at = datetime(2026, 7, 1, 13, 0, 0)
            await db.commit()
        # 第二次恢复（同一天）
        async with self.Session() as db:
            await recover_account(db, 1)
            await db.commit()

        async with self.Session() as db:
            notifications = list(
                (await db.execute(
                    select(NotificationRecord).where(
                        NotificationRecord.type == "account_recovered",
                        NotificationRecord.ref_id == 1,
                    )
                )).scalars().all()
            )
            self.assertEqual(len(notifications), 1, "同账号同天应去重，只保留一条")

    # ==================== 拒绝路径 ====================

    async def test_recover_rejects_nonexistent_account(self):
        """账号不存在 → 抛 XianyuAccountError。"""
        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 99999)
            self.assertIn("不存在", str(ctx.exception))

    async def test_recover_rejects_soft_deleted_account(self):
        """已软删除账号 → 抛 XianyuAccountError。"""
        async with self.Session() as db:
            account = XianyuAccount(
                id=1, nickname="已删除",
                unb="123456", cookies=encrypt_field(VALID_COOKIE),
                status="paused",
                paused_at=datetime(2026, 7, 1, 10, 0, 0),
                updated_at=datetime(2026, 7, 1, 11, 0, 0),
                deleted_at=datetime(2026, 7, 2, 0, 0, 0),
            )
            db.add(account)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 1)
            self.assertIn("已删除", str(ctx.exception))

    async def test_recover_rejects_non_paused_status(self):
        """status != "paused" → 拒绝（账号未熔断无需恢复）。"""
        async with self.Session() as db:
            account = XianyuAccount(
                id=1, nickname="在线",
                unb="123456", cookies=encrypt_field(VALID_COOKIE),
                status="online",
                updated_at=datetime(2026, 7, 1, 11, 0, 0),
            )
            db.add(account)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 1)
            self.assertIn("未处于暂停状态", str(ctx.exception))

    async def test_recover_rejects_when_cookie_not_updated_after_pause(self):
        """updated_at <= paused_at → 拒绝（暂停后未更新 Cookie）。"""
        async with self.Session() as db:
            paused_at = datetime(2026, 7, 1, 12, 0, 0)
            # updated_at 早于 paused_at（Cookie 自暂停后未更新）
            await self._create_paused_account(
                db, account_id=1,
                paused_at=paused_at,
                updated_at=paused_at - timedelta(hours=1),
            )

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 1)
            self.assertIn("更新账号 Cookie", str(ctx.exception))

    async def test_recover_rejects_when_cookie_missing_token(self):
        """Cookie 缺 _m_h5_tk → 拒绝。"""
        async with self.Session() as db:
            await self._create_paused_account(
                db, account_id=1, cookie=COOKIE_MISSING_TOKEN,
            )

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 1)
            self.assertIn("Cookie 校验未通过", str(ctx.exception))

    async def test_recover_rejects_when_cookie_missing_unb(self):
        """Cookie 缺 unb → 拒绝。"""
        async with self.Session() as db:
            await self._create_paused_account(
                db, account_id=1, cookie=COOKIE_MISSING_UNB,
            )

        async with self.Session() as db:
            with self.assertRaises(XianyuAccountError) as ctx:
                await recover_account(db, 1)
            self.assertIn("Cookie 校验未通过", str(ctx.exception))

    # ==================== 通知失败不阻断恢复 ====================

    async def test_notification_failure_does_not_block_recovery(self):
        """通知创建失败时账号恢复仍生效（通知失败仅记日志，不阻断）。"""
        async with self.Session() as db:
            await self._create_paused_account(db, account_id=1)

        # 通知函数在 recover_account 内通过 from ..notification_service import 引入，
        # 因此 patch 在定义处（notification_service 模块）才会生效。
        from app.services import notification_service
        with patch.object(
            notification_service,
            "create_account_recovered_notification",
            side_effect=RuntimeError("通知服务挂了"),
        ):
            async with self.Session() as db:
                account = await recover_account(db, 1)
                await db.commit()
                # 即使通知失败，账号仍应已恢复
                self.assertEqual(account.status, "online")
                self.assertIsNone(account.paused_at)
                self.assertEqual(account.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
