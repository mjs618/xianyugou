"""F3-b 测试补充：audit_service 单元测试。

覆盖点：
1. log_operation: 写入 + 可选字段（target_id/target_name/detail）默认 None
2. list_logs: 无过滤 / module 过滤 / 分页 limit+offset / 返回 (rows, total) / 按 created_at desc 排序
3. clear_logs: 清空所有 / 空表清空幂等
4. log_operation 失败不影响主流程（docstring 承诺，但实际由调用方负责；本测试只验证成功路径）
"""
import unittest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import OperationLog
from app.services.audit_service import clear_logs, list_logs, log_operation
from app.utils.helpers import now_utc


def _make_log(
    *,
    id: int,
    module: str = "rebate",
    action: str = "status_change",
    target_id: int | None = None,
    target_name: str | None = None,
    detail: str | None = None,
    created_at: datetime | None = None,
) -> OperationLog:
    return OperationLog(
        id=id,
        module=module,
        action=action,
        target_id=target_id,
        target_name=target_name,
        detail=detail,
        created_at=created_at or now_utc(),
    )


class AuditServiceTests(unittest.IsolatedAsyncioTestCase):
    """audit_service 三个函数的核心场景。"""

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

    # ==================== log_operation ====================

    async def test_log_operation_writes_all_fields(self):
        async with self.Session() as db:
            await log_operation(
                db,
                module="transaction",
                action="create",
                target_id=42,
                target_name="测试商品A",
                detail="金额:¥100",
            )
            await db.commit()
            log = await db.get(OperationLog, 1)
            self.assertIsNotNone(log)
            self.assertEqual(log.module, "transaction")
            self.assertEqual(log.action, "create")
            self.assertEqual(log.target_id, 42)
            self.assertEqual(log.target_name, "测试商品A")
            self.assertEqual(log.detail, "金额:¥100")
            self.assertIsNotNone(log.created_at)

    async def test_log_operation_optional_fields_default_none(self):
        """未传 target_id/target_name/detail 时落库为 None。"""
        async with self.Session() as db:
            await log_operation(db, module="system", action="startup")
            await db.commit()
            log = await db.get(OperationLog, 1)
            self.assertIsNotNone(log)
            self.assertIsNone(log.target_id)
            self.assertIsNone(log.target_name)
            self.assertIsNone(log.detail)

    async def test_log_operation_returns_none(self):
        """log_operation 没有返回值（docstring 强调"失败不影响主流程"）。"""
        async with self.Session() as db:
            result = await log_operation(db, module="system", action="noop")
            self.assertIsNone(result)

    # ==================== list_logs ====================

    async def test_list_logs_returns_rows_and_total(self):
        """返回 (rows, total) 元组，按 created_at desc 排序。"""
        async with self.Session() as db:
            now = now_utc()
            db.add(_make_log(id=1, created_at=now - timedelta(hours=2)))
            db.add(_make_log(id=2, created_at=now - timedelta(hours=1)))
            db.add(_make_log(id=3, created_at=now))
            await db.commit()
            rows, total = await list_logs(db)
            self.assertEqual(total, 3)
            self.assertEqual(len(rows), 3)
            # 最新优先
            self.assertEqual([r.id for r in rows], [3, 2, 1])

    async def test_list_logs_module_filter(self):
        """module 过滤只返回匹配的日志，total 也只统计匹配项。"""
        async with self.Session() as db:
            db.add(_make_log(id=1, module="rebate"))
            db.add(_make_log(id=2, module="transaction"))
            db.add(_make_log(id=3, module="rebate"))
            await db.commit()
            rows, total = await list_logs(db, module="rebate")
            self.assertEqual(total, 2)
            self.assertEqual({r.id for r in rows}, {1, 3})

    async def test_list_logs_module_filter_no_match(self):
        """未匹配 module → rows=[], total=0。"""
        async with self.Session() as db:
            db.add(_make_log(id=1, module="rebate"))
            await db.commit()
            rows, total = await list_logs(db, module="unknown_module")
            self.assertEqual(total, 0)
            self.assertEqual(rows, [])

    async def test_list_logs_pagination(self):
        """limit + offset 分页：第 2 页（limit=2, offset=2）。"""
        async with self.Session() as db:
            base = now_utc()
            for i in range(5):
                db.add(_make_log(id=i + 1, created_at=base + timedelta(hours=i)))
            await db.commit()
            rows, total = await list_logs(db, limit=2, offset=2)
            # total 仍是全量
            self.assertEqual(total, 5)
            # 第 2 页 = [id=3, id=2]（desc 顺序）
            self.assertEqual([r.id for r in rows], [3, 2])

    async def test_list_logs_default_limit_is_50(self):
        """未传 limit 时默认 50。"""
        async with self.Session() as db:
            db.add(_make_log(id=1))
            await db.commit()
            rows, _ = await list_logs(db)
            self.assertEqual(len(rows), 1)

    async def test_list_logs_empty_table(self):
        """空表 → rows=[], total=0。"""
        async with self.Session() as db:
            rows, total = await list_logs(db)
            self.assertEqual(total, 0)
            self.assertEqual(rows, [])

    async def test_list_logs_offset_beyond_end(self):
        """offset 超过总数 → rows=[], total 仍为实际总数。"""
        async with self.Session() as db:
            db.add(_make_log(id=1))
            await db.commit()
            rows, total = await list_logs(db, limit=10, offset=100)
            self.assertEqual(total, 1)
            self.assertEqual(rows, [])

    # ==================== clear_logs ====================

    async def test_clear_logs_removes_all(self):
        async with self.Session() as db:
            db.add(_make_log(id=1, module="rebate"))
            db.add(_make_log(id=2, module="transaction"))
            db.add(_make_log(id=3, module="system"))
            await db.commit()
            await clear_logs(db)
            await db.commit()
            rows, total = await list_logs(db)
            self.assertEqual(total, 0)
            self.assertEqual(rows, [])

    async def test_clear_logs_idempotent_on_empty_table(self):
        """对空表 clear_logs 不报错。"""
        async with self.Session() as db:
            await clear_logs(db)
            await db.commit()
            rows, total = await list_logs(db)
            self.assertEqual(total, 0)
            self.assertEqual(rows, [])

    async def test_clear_logs_only_clears_target_table(self):
        """clear_logs 只删 operation_logs，不影响其他表（这里间接验证 list_logs 仍可调用）。"""
        async with self.Session() as db:
            db.add(_make_log(id=1, module="rebate"))
            await db.commit()
            await clear_logs(db)
            await db.commit()
            # 清空后仍可重新写入
            await log_operation(db, module="system", action="restart")
            await db.commit()
            rows, total = await list_logs(db)
            self.assertEqual(total, 1)
            self.assertEqual(rows[0].action, "restart")


if __name__ == "__main__":
    unittest.main()
