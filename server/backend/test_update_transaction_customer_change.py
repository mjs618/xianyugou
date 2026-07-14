"""E8 回归测试：update_transaction 客户变更级联。

修复前：customer_id 不在 setattr 列表，导致前端传 customer_id 时
- 交易归属不变（仍是老客户）
- 但 patch["customer_id"] != t.customer_id 判断触发对新客户 recalc
- 新客户统计被污染（多算了一笔不存在的交易）

修复后：
1. customer_id 进入 setattr 列表，交易归属真正变更
2. 级联顺序：先 recalc 老客户（扣除这笔），再 recalc 新客户（加上这笔）
3. 客户不变时仍按原逻辑 recalc（如价格变更）
"""
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, Transaction
from app.services.transaction_service import update_transaction


class UpdateTransactionCustomerChangeTests(unittest.IsolatedAsyncioTestCase):
    """update_transaction 客户变更与级联重算。"""

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

    async def _create_customer(self, db, *, customer_id: int, nickname: str) -> Customer:
        c = Customer(id=customer_id, xianyu_nickname=nickname)
        db.add(c)
        await db.flush()
        return c

    async def _create_transaction(
        self, db, *, tx_id: int, customer_id: int, sale_price: float = 100.0,
        cost_price: float = 50.0, status: str = "completed",
    ) -> Transaction:
        tx = Transaction(
            id=tx_id,
            customer_id=customer_id,
            product_name="测试商品",
            sale_price=sale_price,
            cost_price=cost_price,
            profit=sale_price - cost_price,
            trade_at=datetime(2026, 7, 1, 10, 0, 0),
            shipped_at=datetime(2026, 7, 1, 11, 0, 0),
            status=status,
            warranty_days=30,
            channel="xianyu",
        )
        db.add(tx)
        await db.flush()
        return tx

    # ==================== 修复核心：客户变更真正生效 ====================

    async def test_customer_id_change_actually_updates_transaction(self):
        """修复核心：customer_id 进入 setattr 列表，交易归属真正变更。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        # update 把交易从客户 A 切到客户 B
        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2})
            await db.commit()

        async with self.Session() as db:
            tx = await db.get(Transaction, 10)
            self.assertEqual(tx.customer_id, 2, "交易归属应变为客户 B")

    async def test_customer_change_recalculates_old_customer_stats(self):
        """客户变更后老客户统计扣除这笔交易。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2})
            await db.commit()

        async with self.Session() as db:
            a = await db.get(Customer, 1)
            self.assertEqual(a.total_spent, 0.0, "老客户累计消费应扣除这笔交易")
            self.assertEqual(a.trade_count, 0, "老客户交易笔数应扣除这笔交易")

    async def test_customer_change_recalculates_new_customer_stats(self):
        """客户变更后新客户统计加上这笔交易。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2})
            await db.commit()

        async with self.Session() as db:
            b = await db.get(Customer, 2)
            self.assertEqual(b.total_spent, 100.0, "新客户累计消费应加上这笔交易")
            self.assertEqual(b.trade_count, 1, "新客户交易笔数应加上这笔交易")

    async def test_customer_change_cascade_order_old_before_new(self):
        """级联顺序：先 recalc 老客户、再 recalc 新客户。

        场景：同时改 customer_id 和 sale_price。
        修复后老客户不应看到新价格（统计应基于原价 100），新客户应看到新价格 200。
        """
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2, "sale_price": 200.0})
            await db.commit()

        async with self.Session() as db:
            a = await db.get(Customer, 1)
            b = await db.get(Customer, 2)
            # 老客户：交易已不属于他，统计应为 0（无论价格怎么改）
            self.assertEqual(a.total_spent, 0.0)
            self.assertEqual(a.trade_count, 0)
            # 新客户：交易归属他，统计应基于新价格 200
            self.assertEqual(b.total_spent, 200.0)
            self.assertEqual(b.trade_count, 1)

    async def test_customer_change_with_price_change_keeps_correct_profit(self):
        """客户变更 + 价格变更：profit 字段同步重算。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0, cost_price=50.0)
            await db.commit()

        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2, "sale_price": 300.0, "cost_price": 100.0})
            await db.commit()

        async with self.Session() as db:
            tx = await db.get(Transaction, 10)
            self.assertEqual(tx.sale_price, 300.0)
            self.assertEqual(tx.cost_price, 100.0)
            self.assertEqual(tx.profit, 200.0)

    # ==================== 客户不变时仍 recalc ====================

    async def test_price_change_without_customer_change_recalcs_customer(self):
        """客户不变 + 价格变更：客户统计同步更新（原行为不破坏）。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        # 客户 A 初始 total_spent=100（recalc 一次）
        async with self.Session() as db:
            from app.services.customer_service import recalc_customer_stats
            await recalc_customer_stats(db, 1)
            await db.commit()
            a = await db.get(Customer, 1)
            self.assertEqual(a.total_spent, 100.0)

        # 改价格到 300，客户不变
        async with self.Session() as db:
            await update_transaction(db, 10, {"sale_price": 300.0})
            await db.commit()

        async with self.Session() as db:
            a = await db.get(Customer, 1)
            self.assertEqual(a.total_spent, 300.0, "客户不变时统计应同步新价格")
            self.assertEqual(a.trade_count, 1)

    async def test_other_field_change_without_customer_change_recalcs_customer(self):
        """非客户字段变更（如 status）也触发 recalc。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_transaction(
                db, tx_id=10, customer_id=1, sale_price=100.0, status="pending",
            )
            await db.commit()
            # pending 不计入 total_spent（看 recalc 实现：status='closed' 才排除，pending 也计入）
            # 注：recalc 只排除 closed，pending 也算累计

        async with self.Session() as db:
            await update_transaction(db, 10, {"status": "completed"})
            await db.commit()

        async with self.Session() as db:
            a = await db.get(Customer, 1)
            self.assertEqual(a.trade_count, 1)
            self.assertEqual(a.total_spent, 100.0)

    # ==================== 客户不变时不应误触发双重 recalc ====================

    async def test_same_customer_id_no_duplicate_recalc(self):
        """传相同的 customer_id 不应触发老客户 recalc（性能回归测试）。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        # 监控 recalc_customer_stats 调用次数
        from app.services import transaction_service
        call_count = 0
        original_recalc = transaction_service.recalc_customer_stats

        async def counting_recalc(db, cid):
            nonlocal call_count
            call_count += 1
            return await original_recalc(db, cid)

        with patch.object(
            transaction_service, "recalc_customer_stats", side_effect=counting_recalc
        ):
            async with self.Session() as db:
                await update_transaction(db, 10, {"customer_id": 1, "sale_price": 200.0})
                await db.commit()

        self.assertEqual(call_count, 1, "客户不变时只应 recalc 一次（性能保证）")

    async def test_customer_change_triggers_two_recalcs(self):
        """客户变更触发两次 recalc（老 + 新）。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1, sale_price=100.0)
            await db.commit()

        from app.services import transaction_service
        call_count = 0
        original_recalc = transaction_service.recalc_customer_stats

        async def counting_recalc(db, cid):
            nonlocal call_count
            call_count += 1
            return await original_recalc(db, cid)

        with patch.object(
            transaction_service, "recalc_customer_stats", side_effect=counting_recalc
        ):
            async with self.Session() as db:
                await update_transaction(db, 10, {"customer_id": 2})
                await db.commit()

        self.assertEqual(call_count, 2, "客户变更时应 recalc 两次（老 + 新）")

    # ==================== 版本号 + updated_at ====================

    async def test_customer_change_increments_version(self):
        """客户变更时 version + 1。"""
        async with self.Session() as db:
            await self._create_customer(db, customer_id=1, nickname="客户A")
            await self._create_customer(db, customer_id=2, nickname="客户B")
            await self._create_transaction(db, tx_id=10, customer_id=1)
            await db.commit()
            original_version = (await db.get(Transaction, 10)).version

        async with self.Session() as db:
            await update_transaction(db, 10, {"customer_id": 2})
            await db.commit()

        async with self.Session() as db:
            tx = await db.get(Transaction, 10)
            self.assertEqual(tx.version, original_version + 1)


if __name__ == "__main__":
    unittest.main()
