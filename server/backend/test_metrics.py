"""P1-3 修复验证：监控指标端点。

覆盖：
1. /api/metrics 不带 token 返回 401（受中间件保护）
2. 带 token 返回 200 且字段完整（accounts / sync / backup / notifications_unread / scheduler_running）
3. 字段类型符合预期（账号总数 int、未读数 int、调度器运行 bool）
4. 备份相关字段存在（last_backup_at 可空、backup_count int、backup_dir_exists bool）
"""
import unittest
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.security import token as token_module


class FakeResult:
    """模拟 SQLAlchemy Result 的链式调用。"""

    def __init__(self, items=None, scalar_value=0, single=None):
        self._items = items or []
        self._scalar_value = scalar_value
        self._single = single

    def scalars(self):
        return self

    def all(self):
        return list(self._items)

    def scalar_one_or_none(self):
        return self._single

    def scalar(self):
        return self._scalar_value


class FakeDb:
    """模拟 AsyncSession：execute 按预设顺序返回 FakeResult。"""

    def __init__(self, results=None):
        self._results = list(results) if results else []
        self.execute_calls = 0

    async def execute(self, stmt):
        self.execute_calls += 1
        if self._results:
            return self._results.pop(0)
        # 默认返回空结果
        return FakeResult()


@pytest.mark.token_auth
class MetricsEndpointTests(unittest.IsolatedAsyncioTestCase):
    """测 /api/metrics 端点本身：用 @pytest.mark.token_auth 标记跳过 conftest 的 autouse 绕过。"""

    async def asyncSetUp(self):
        # 用固定的测试 token，避免影响真实 data/api.token
        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "test-metrics-token-xyz"
        self.test_token = "test-metrics-token-xyz"

    async def asyncTearDown(self):
        token_module.get_api_token = self._original_get
        # 清理 dependency_overrides
        app.dependency_overrides.pop(get_db, None)

    def _override_get_db(self, db: FakeDb):
        """用 FastAPI dependency_overrides 覆盖 get_db，避免触碰真实 SQLite。

        FastAPI 的 Depends 期望的是 generator function（直接 yield），不是
        @asynccontextmanager 装饰的对象。这里用 async generator 直接 yield。
        """
        async def fake_get_db():
            yield db
        app.dependency_overrides[get_db] = fake_get_db

    async def test_metrics_without_token_returns_401(self):
        """P1-3: /api/metrics 不在白名单中，必须要求 X-API-Token。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/metrics")
        self.assertEqual(response.status_code, 401)

    async def test_metrics_with_wrong_token_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/metrics", headers={"X-API-Token": "wrong-token"}
            )
        self.assertEqual(response.status_code, 401)

    async def test_metrics_with_correct_token_returns_200_and_full_schema(self):
        """带正确 token 返回 200 且响应包含所有字段。"""
        # get_metrics 中有 5 次 db.execute：
        # 1) account_status_rows 2) sync_rows 3) last_log 4) unread 5) ... 实际是 4 次
        # 为简单起见，FakeDb.execute 默认返回空结果
        fake_db = FakeDb()
        self._override_get_db(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # mock sync_scheduler.running 避免触发真实调度器
            with patch("app.services.sync_scheduler.scheduler") as mock_sync_sched:
                mock_sync_sched.running = True
                # mock backup_scheduler 方法
                with patch("app.maintenance.backup_scheduler.scheduler") as mock_backup:
                    mock_backup._last_backup_at.return_value = None
                    mock_backup._count_backups.return_value = 0
                    mock_backup._backup_dir.exists.return_value = False

                    response = await client.get(
                        "/api/metrics",
                        headers={"X-API-Token": self.test_token},
                    )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        # 顶层字段
        self.assertIn("timestamp", body)
        self.assertIn("accounts", body)
        self.assertIn("sync", body)
        self.assertIn("backup", body)
        self.assertIn("notifications_unread", body)
        self.assertIn("scheduler_running", body)
        # accounts 子字段
        self.assertEqual(
            set(body["accounts"].keys()),
            {"total", "online", "paused", "invalid"},
        )
        # sync 子字段
        self.assertEqual(
            set(body["sync"].keys()),
            {
                "last_24h_success", "last_24h_failed",
                "last_24h_fetched_orders", "last_24h_created_transactions",
                "last_error", "last_sync_at",
            },
        )
        # backup 子字段
        self.assertEqual(
            set(body["backup"].keys()),
            {"last_backup_at", "backup_count", "backup_dir_exists"},
        )
        # 类型断言
        self.assertIsInstance(body["accounts"]["total"], int)
        self.assertIsInstance(body["notifications_unread"], int)
        self.assertIsInstance(body["scheduler_running"], bool)
        self.assertIsInstance(body["backup"]["backup_count"], int)
        self.assertIsInstance(body["backup"]["backup_dir_exists"], bool)

    async def test_metrics_returns_zero_values_for_empty_db(self):
        """空数据库时返回 0 值，不抛异常。"""
        fake_db = FakeDb()
        self._override_get_db(fake_db)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("app.services.sync_scheduler.scheduler") as mock_sync_sched:
                mock_sync_sched.running = False
                with patch("app.maintenance.backup_scheduler.scheduler") as mock_backup:
                    mock_backup._last_backup_at.return_value = None
                    mock_backup._count_backups.return_value = 0
                    mock_backup._backup_dir.exists.return_value = False

                    response = await client.get(
                        "/api/metrics",
                        headers={"X-API-Token": self.test_token},
                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["accounts"]["total"], 0)
        self.assertEqual(body["accounts"]["online"], 0)
        self.assertEqual(body["sync"]["last_24h_success"], 0)
        self.assertEqual(body["sync"]["last_24h_failed"], 0)
        self.assertEqual(body["sync"]["last_24h_fetched_orders"], 0)
        self.assertEqual(body["sync"]["last_24h_created_transactions"], 0)
        self.assertEqual(body["backup"]["backup_count"], 0)
        self.assertFalse(body["backup"]["backup_dir_exists"])
        self.assertEqual(body["notifications_unread"], 0)
        self.assertFalse(body["scheduler_running"])


if __name__ == "__main__":
    unittest.main()

