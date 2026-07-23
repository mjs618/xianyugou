"""P3 安全调度：账号熔断恢复流程测试。

对应设计文档：「暂停后必须人工更新 Cookie、通过只读校验并点击恢复」。
"""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.services.xianyu import account_service
from app.services.xianyu.account_service import XianyuAccountError


class FakeDb:
    def __init__(self, account):
        self._account = account

    async def get(self, model, account_id):
        return self._account

    async def flush(self):
        pass


class RecoverAccountTests(unittest.IsolatedAsyncioTestCase):
    def _make_account(self, *, status="paused", paused_at=None, updated_at=None, valid_cookie=True):
        return SimpleNamespace(
            id=1,
            nickname="test",
            cookies="encrypted-cookie",
            unb="12345",
            status=status,
            last_error="登录态失效",
            paused_at=paused_at,
            updated_at=updated_at,
            consecutive_failures=3,
            auto_sync_enabled=True,
            auto_sync_interval_minutes=120,
            deleted_at=None,
        )

    async def test_recover_requires_paused_status(self):
        account = self._make_account(status="online")
        with self.assertRaises(XianyuAccountError) as ctx:
            await account_service.recover_account(FakeDb(account), 1)
        self.assertIn("未处于暂停状态", str(ctx.exception))

    async def test_recover_requires_cookie_update_after_pause(self):
        # updated_at 早于 paused_at：暂停后未更新 Cookie
        paused = datetime(2026, 7, 11, 10, 0, 0)
        account = self._make_account(paused_at=paused, updated_at=paused - timedelta(minutes=1))
        with self.assertRaises(XianyuAccountError) as ctx:
            await account_service.recover_account(FakeDb(account), 1)
        self.assertIn("更新账号 Cookie", str(ctx.exception))
        self.assertEqual(account.status, "paused")

    async def test_recover_rejects_invalid_cookie_format(self):
        paused = datetime(2026, 7, 11, 10, 0, 0)
        account = self._make_account(paused_at=paused, updated_at=paused + timedelta(minutes=5))
        with patch.object(account_service, "decrypt_field", return_value="bad-cookie"):
            with patch.object(
                account_service,
                "validate_cookies",
                return_value=(False, None, "缺少 unb 字段"),
            ):
                with self.assertRaises(XianyuAccountError) as ctx:
                    await account_service.recover_account(FakeDb(account), 1)
        self.assertIn("Cookie 校验未通过", str(ctx.exception))
        self.assertEqual(account.status, "paused")

    async def test_recover_clears_pause_state_on_valid_cookie(self):
        paused = datetime(2026, 7, 11, 10, 0, 0)
        account = self._make_account(paused_at=paused, updated_at=paused + timedelta(minutes=5))
        account.nickname = "测试账号"
        with patch.object(account_service, "decrypt_field", return_value="unb=12345; _m_h5_tk=token_ts"):
            with patch.object(
                account_service,
                "validate_cookies",
                return_value=(True, "12345", "ok"),
            ):
                with patch(
                    "app.services.notification_service.create_account_recovered_notification"
                ):
                    result = await account_service.recover_account(FakeDb(account), 1)
        self.assertEqual(result.status, "online")
        self.assertIsNone(result.paused_at)
        self.assertEqual(result.consecutive_failures, 0)
        self.assertIsNone(result.last_error)

    async def test_recover_creates_notification(self):
        """P3 告警：账号恢复时应创建 account_recovered 通知。"""
        paused = datetime(2026, 7, 11, 10, 0, 0)
        account = self._make_account(paused_at=paused, updated_at=paused + timedelta(minutes=5))
        account.nickname = "恢复测试号"
        with patch.object(account_service, "decrypt_field", return_value="unb=12345; _m_h5_tk=token_ts"):
            with patch.object(
                account_service,
                "validate_cookies",
                return_value=(True, "12345", "ok"),
            ):
                with patch(
                    "app.services.notification_service.create_account_recovered_notification"
                ) as mock_notify:
                    await account_service.recover_account(FakeDb(account), 1)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        self.assertEqual(call_args.args[1], 1)  # account_id
        self.assertEqual(call_args.args[2], "恢复测试号")  # nickname

    async def test_recover_nonexistent_account_raises(self):
        class EmptyDb:
            async def get(self, model, account_id):
                return None

            async def flush(self):
                pass

        with self.assertRaises(XianyuAccountError):
            await account_service.recover_account(EmptyDb(), 999)

    async def test_cookie_update_restores_invalid_account_but_not_paused_account(self):
        with patch.object(
            account_service,
            "validate_cookies",
            return_value=(True, "12345", "ok"),
        ), patch.object(account_service, "encrypt_field", return_value="encrypted-new"):
            invalid = self._make_account(status="invalid")
            await account_service.update_account(
                FakeDb(invalid), 1, {"cookies": "valid-cookie"}
            )
            paused = self._make_account(status="paused")
            await account_service.update_account(
                FakeDb(paused), 1, {"cookies": "valid-cookie"}
            )

        self.assertEqual(invalid.status, "online")
        self.assertIsNone(invalid.last_error)
        self.assertEqual(invalid.consecutive_failures, 0)
        self.assertEqual(paused.status, "paused")


if __name__ == "__main__":
    unittest.main()
