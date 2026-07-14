"""D4 测试补充：aftersales_service.update_status 状态回滚。

验证售后工单关闭后交易状态恢复逻辑（P-20 修复）：
1. 工单 resolved/closed 时若该交易无其他 open 工单 → 恢复交易状态
2. 恢复值取「最早工单」的 original_transaction_status，缺失则回退 completed
3. 仍有 pending/processing 工单时不恢复
4. 多工单场景下 earliest 工单的 original_transaction_status 胜出
5. resolved/closed 时计算 duration_hours
6. pending → processing 等非终态切换不触发恢复
"""
import unittest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AfterSales, Customer, Transaction
from app.services.aftersales_service import (
    AfterSalesError,
    create_aftersales,
    update_status,
)
from app.utils.helpers import now_utc


class AftersalesStatusRollbackTests(unittest.IsolatedAsyncioTestCase):
    """update_status 在工单关闭时恢复交易状态的核心场景。"""

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

    async def _create_customer_and_transaction(
        self,
        db,
        *,
        customer_id: int = 1,
        tx_id: int = 1,
        status: str = "completed",
        nickname: str = "客户A",
    ) -> tuple[Customer, Transaction]:
        """创建客户 + 交易（指定 id，测试用）。"""
        c = Customer(id=customer_id, xianyu_nickname=nickname)
        db.add(c)
        tx = Transaction(
            id=tx_id,
            customer_id=customer_id,
            product_name="测试商品",
            sale_price=100.0,
            cost_price=50.0,
            profit=50.0,
            trade_at=datetime(2026, 7, 1, 10, 0, 0),
            status=status,
            warranty_days=30,
            channel="xianyu",
        )
        db.add(tx)
        await db.flush()
        return c, tx

    # ==================== 单工单：resolved/closed 触发恢复 ====================

    async def test_resolve_single_ticket_restores_transaction_to_original_status(self):
        """resolved：单工单 → 交易恢复到 original_transaction_status。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="质量问题")
            await db.commit()
            # 工单创建时交易被切到 aftersales，并记录 original=completed
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales")
            self.assertEqual(ticket.original_transaction_status, "completed")

            # 解决工单 → 交易恢复到 completed
            await update_status(db, ticket.id, "resolved", solution_type="remote")
            await db.commit()

            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "completed")

    async def test_close_single_ticket_restores_transaction_to_original_status(self):
        """closed：单工单 → 交易恢复到 original_transaction_status。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="损坏")
            await db.commit()

            await update_status(db, ticket.id, "closed", solution_type="refund")
            await db.commit()

            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "completed")

    async def test_resolve_restores_to_pending_when_original_was_pending(self):
        """original_transaction_status=pending 时恢复到 pending。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="pending")
            await db.commit()
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="缺件")
            await db.commit()
            # 工单创建后交易切到 aftersales，original=pending
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales")
            self.assertEqual(ticket.original_transaction_status, "pending")

            await update_status(db, ticket.id, "resolved")
            await db.commit()

            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "pending")

    async def test_resolve_falls_back_to_completed_when_original_status_missing(self):
        """original_transaction_status=None（交易已在 aftersales）→ 回退 completed。

        场景：交易已有工单处于 aftersales，再开第二个工单 → 第二个工单的
        original_transaction_status 为 None。若此时第二个工单关闭且无其他 open 工单，
        恢复值应回退为 "completed"。
        """
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            # 第一个工单：交易 completed → aftersales，记录 original=completed
            t1 = await create_aftersales(db, transaction_id=1, issue_desc="问题A")
            await db.commit()
            # 第二个工单：交易已处于 aftersales，original_transaction_status=None
            t2 = await create_aftersales(db, transaction_id=1, issue_desc="问题B")
            await db.commit()
            self.assertIsNone(t2.original_transaction_status)

            # 先关闭第一个工单（仍有 t2 open，不恢复）
            await update_status(db, t1.id, "resolved")
            await db.commit()
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales", "仍有 open 工单时不应恢复")

            # 关闭第二个工单：earliest=t1（original=completed）→ 恢复到 completed
            await update_status(db, t2.id, "resolved")
            await db.commit()
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "completed")

    # ==================== 多工单：恢复时机与 earliest 选择 ====================

    async def test_resolve_with_other_open_tickets_does_not_restore(self):
        """仍有 pending/processing 工单时不恢复交易状态。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            t1 = await create_aftersales(db, transaction_id=1, issue_desc="问题A")
            await db.commit()
            t2 = await create_aftersales(db, transaction_id=1, issue_desc="问题B")
            await db.commit()

            # 解决 t1（t2 仍 pending）→ 不应恢复交易
            await update_status(db, t1.id, "resolved")
            await db.commit()

            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales", "t2 仍 open，交易应保持 aftersales")

            # 解决 t2（无 open 了）→ 恢复交易
            await update_status(db, t2.id, "resolved")
            await db.commit()
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "completed")

    async def test_earliest_ticket_original_status_wins_when_multiple_closed(self):
        """多工单场景：取最早工单的 original_transaction_status。

        场景：交易 pending → 开 t1（original=pending）→ 交易切 aftersales →
        开 t2（original_transaction_status=None）→ 关闭 t1（仍有 t2 open，不恢复）→
        关闭 t2（无 open 了，earliest=t1，original=pending）→ 恢复到 pending。
        """
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="pending")
            await db.commit()
            t1 = await create_aftersales(db, transaction_id=1, issue_desc="问题A")
            await db.commit()
            # 强制让 t2 的 created_at 比 t1 晚一秒，确保 earliest 查询返回 t1
            t2 = AfterSales(
                transaction_id=1,
                issue_desc="问题B",
                status="pending",
                attachments=[],
                original_transaction_status=None,
                created_at=datetime(2026, 7, 1, 11, 0, 0),
            )
            db.add(t2)
            await db.commit()

            # 关闭 t1（t2 仍 open）
            await update_status(db, t1.id, "resolved")
            await db.commit()
            # 关闭 t2（无 open，earliest=t1，original=pending）
            await update_status(db, t2.id, "resolved")
            await db.commit()

            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "pending", "earliest=t1 的 original=pending 应胜出")

    async def test_processing_ticket_counts_as_open(self):
        """processing 状态也算 open：解决 pending 工单但仍有 processing 工单时不恢复。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            t1 = await create_aftersales(db, transaction_id=1, issue_desc="问题A")
            await db.commit()
            t2 = await create_aftersales(db, transaction_id=1, issue_desc="问题B")
            await db.commit()
            # t2 切到 processing
            await update_status(db, t2.id, "processing")
            await db.commit()

            # 解决 t1（t2 仍 processing）→ 不恢复
            await update_status(db, t1.id, "resolved")
            await db.commit()
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales")

    # ==================== 非终态切换 + 字段写入 ====================

    async def test_pending_to_processing_does_not_restore(self):
        """pending → processing 不触发交易恢复。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="问题")
            await db.commit()

            await update_status(db, ticket.id, "processing")
            await db.commit()
            tx = await db.get(Transaction, 1)
            self.assertEqual(tx.status, "aftersales", "非终态切换不应恢复交易")

    async def test_resolve_writes_duration_hours(self):
        """resolved 时计算 duration_hours = (resolved_at - created_at) 小时数。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            # 工单 created_at 由 server_default 设为 now，我们手动覆盖为 5 小时前
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="问题")
            await db.commit()
            five_hours_ago = now_utc() - timedelta(hours=5)
            ticket.created_at = five_hours_ago
            await db.commit()

            await update_status(db, ticket.id, "resolved")
            await db.commit()

            refreshed = await db.get(AfterSales, ticket.id)
            self.assertIsNotNone(refreshed.resolved_at)
            self.assertIsNotNone(refreshed.duration_hours)
            # 5 小时上下，舍入误差 ±1
            self.assertAlmostEqual(refreshed.duration_hours, 5, delta=1)

    async def test_resolve_writes_solution_fields(self):
        """resolved 时写入 solution_type 与 solution_desc。"""
        async with self.Session() as db:
            await self._create_customer_and_transaction(db, status="completed")
            await db.commit()
            ticket = await create_aftersales(db, transaction_id=1, issue_desc="问题")
            await db.commit()

            await update_status(
                db, ticket.id, "resolved",
                solution_type="reship",
                solution_desc="已补发新货",
            )
            await db.commit()

            refreshed = await db.get(AfterSales, ticket.id)
            self.assertEqual(refreshed.status, "resolved")
            self.assertEqual(refreshed.solution_type, "reship")
            self.assertEqual(refreshed.solution_desc, "已补发新货")

    async def test_update_status_rejects_nonexistent_ticket(self):
        """不存在的 ticket_id 抛 AfterSalesError。"""
        async with self.Session() as db:
            with self.assertRaises(AfterSalesError):
                await update_status(db, 99999, "resolved")


if __name__ == "__main__":
    unittest.main()
