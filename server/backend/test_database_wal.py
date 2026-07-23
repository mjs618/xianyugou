"""P2-1 修复验证：SQLite WAL 模式与相关 pragma。"""
import unittest

from sqlalchemy import text

from app.config import settings
from app.database import engine


class SQLiteWalTests(unittest.IsolatedAsyncioTestCase):
    """验证 SQLite 引擎在每次连接时应用了 WAL pragma。

    用真实 in-memory / 文件 SQLite 引擎，让 SQLAlchemy 实际打开连接并执行 PRAGMA。
    若 database.py 中的 connect 监听器未生效，PRAGMA 会返回默认值（delete / 0）。
    """

    async def test_journal_mode_is_wal(self):
        """PRAGMA journal_mode 应为 'wal'。"""
        if not settings.is_sqlite:
            self.skipTest("仅 SQLite 适用")
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
        self.assertIsNotNone(mode)
        self.assertEqual(mode.lower(), "wal")

    async def test_busy_timeout_is_5000(self):
        """PRAGMA busy_timeout 应为 5000（毫秒）。"""
        if not settings.is_sqlite:
            self.skipTest("仅 SQLite 适用")
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
        self.assertEqual(result.scalar(), 5000)

    async def test_synchronous_is_normal(self):
        """PRAGMA synchronous 应为 1（NORMAL）。"""
        if not settings.is_sqlite:
            self.skipTest("仅 SQLite 适用")
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
        # SQLite: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA
        self.assertEqual(result.scalar(), 1)

    async def test_pragmas_applied_on_every_new_connection(self):
        """每次新连接都应应用 pragma（验证监听器在每次 connect 时触发，而非仅首次）。"""
        if not settings.is_sqlite:
            self.skipTest("仅 SQLite 适用")
        # 打开多个连接，每次都验证
        for _ in range(3):
            async with engine.connect() as conn:
                result = await conn.execute(text("PRAGMA journal_mode"))
                mode = result.scalar()
            self.assertEqual(mode.lower(), "wal")


if __name__ == "__main__":
    unittest.main()
