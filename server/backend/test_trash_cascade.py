"""D6 测试补充：trash_service cascade 流程。

验证回收站彻底删除（purge_*）的级联清理：
1. purge_customer 级联硬删除：交易 / 售后工单 / 返利 / 质保延长 / 推荐关系 / 标签关系
2. purge_transaction 级联硬删除：售后工单 / 返利 / 质保延长
3. purge_after_sales 仅删自身
4. purge_* 拒绝非软删除对象（必须先软删除）
5. purge_* 不存在的对象抛 ValueError
6. restore_* 校验：未软删除拒绝恢复、关联资源被删时拒绝
7. restore_customer 校验昵称冲突
"""
import unittest
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import (
    AfterSales,
    Customer,
    CustomerLink,
    CustomerTag,
    CustomerTagRelation,
    RebateRecord,
    Transaction,
    WarrantyExtension,
)
from app.services.trash_service import (
    purge_after_sales,
    purge_customer,
    purge_transaction,
    restore_after_sales,
    restore_customer,
    restore_transaction,
)


class TrashCascadeTests(unittest.IsolatedAsyncioTestCase):
    """trash_service 级联硬删除与恢复校验。"""

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

    # ==================== 测试数据构造 ====================

    async def _seed_full_chain(self, db) -> dict:
        """构造「客户→交易→售后/返利/质保延长 + 推荐关系 + 标签」全链路数据。

        所有对象都已软删除（满足 purge 前置条件）。
        """
        now = datetime(2026, 7, 1, 10, 0, 0)
        # 客户：1（主客户）+ 2（推荐人，仅用于 CustomerLink）
        c1 = Customer(
            id=1, xianyu_nickname="客户A",
            deleted_at=now,
        )
        c2 = Customer(id=2, xianyu_nickname="推荐人")
        db.add_all([c1, c2])
        # 交易
        t1 = Transaction(
            id=10, customer_id=1, product_name="商品A",
            sale_price=100.0, cost_price=50.0, profit=50.0,
            trade_at=now, status="completed",
            warranty_days=30, channel="xianyu",
            deleted_at=now,
        )
        db.add(t1)
        # 售后工单
        a1 = AfterSales(
            id=100, transaction_id=10, issue_desc="质量问题",
            status="pending", attachments=[],
            deleted_at=now, created_at=now,
        )
        db.add(a1)
        # 返利
        r1 = RebateRecord(
            id=200, referrer_id=2, buyer_id=1, transaction_id=10,
            amount=5.0, rate=0.1, status="pending",
        )
        db.add(r1)
        # 质保延长
        w1 = WarrantyExtension(
            id=300, transaction_id=10,
            old_end=now, new_end=now, extended_days=7,
        )
        db.add(w1)
        # 推荐关系（涉及 c1）
        link1 = CustomerLink(
            id=400, referrer_id=2, buyer_id=1, transaction_id=10, level=0,
        )
        db.add(link1)
        # 标签定义 + 关联关系（涉及 c1）
        tag1 = CustomerTag(id=1, name="vip")
        db.add(tag1)
        rel1 = CustomerTagRelation(id=500, customer_id=1, tag_id=1)
        db.add(rel1)
        await db.commit()
        return {
            "customer_id": 1,
            "transaction_id": 10,
            "aftersales_id": 100,
            "rebate_id": 200,
            "warranty_id": 300,
            "link_id": 400,
            "tag_relation_id": 500,
            "referrer_id": 2,
        }

    async def _count(self, db, model) -> int:
        return len((await db.execute(select(model))).scalars().all())

    # ==================== purge_customer ====================

    async def test_purge_customer_cascades_all_related(self):
        """purge_customer 级联删除：交易/售后/返利/质保延长/推荐关系/标签关系 + 客户本体。"""
        async with self.Session() as db:
            ids = await self._seed_full_chain(db)

        async with self.Session() as db:
            await purge_customer(db, ids["customer_id"])
            await db.commit()

        async with self.Session() as db:
            self.assertEqual(await self._count(db, Customer), 1, "应只剩推荐人 c2")
            self.assertIsNone(await db.get(Customer, ids["customer_id"]))
            self.assertIsNotNone(await db.get(Customer, ids["referrer_id"]))
            # 级联清理
            self.assertEqual(await self._count(db, Transaction), 0)
            self.assertEqual(await self._count(db, AfterSales), 0)
            self.assertEqual(await self._count(db, RebateRecord), 0)
            self.assertEqual(await self._count(db, WarrantyExtension), 0)
            self.assertEqual(await self._count(db, CustomerLink), 0, "推荐关系涉及 c1 应删")
            self.assertEqual(await self._count(db, CustomerTagRelation), 0, "标签关系涉及 c1 应删")
            # 标签定义本体不删（仅删关系）
            self.assertIsNotNone(await db.get(CustomerTag, 1))

    async def test_purge_customer_rejects_non_soft_deleted(self):
        """purge_customer 拒绝未软删除的客户。"""
        async with self.Session() as db:
            c = Customer(id=1, xianyu_nickname="未删除客户")
            db.add(c)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await purge_customer(db, 1)
            self.assertIn("仅可彻底删除回收站", str(ctx.exception))

    async def test_purge_customer_rejects_nonexistent(self):
        """purge_customer 不存在的客户抛 ValueError。"""
        async with self.Session() as db:
            with self.assertRaises(ValueError):
                await purge_customer(db, 99999)

    async def test_purge_customer_preserves_other_customers_relations(self):
        """purge_customer 不影响其他客户的关联数据。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            # c1 软删，c2 在线
            c1 = Customer(id=1, xianyu_nickname="客户A", deleted_at=now)
            c2 = Customer(id=2, xianyu_nickname="客户B")
            db.add_all([c1, c2])
            # c1 和 c2 各有交易
            t1 = Transaction(
                id=10, customer_id=1, product_name="商品A",
                sale_price=100.0, cost_price=50.0, profit=50.0,
                trade_at=now, status="completed",
                warranty_days=30, channel="xianyu",
                deleted_at=now,
            )
            t2 = Transaction(
                id=11, customer_id=2, product_name="商品B",
                sale_price=200.0, cost_price=100.0, profit=100.0,
                trade_at=now, status="completed",
                warranty_days=30, channel="xianyu",
            )
            db.add_all([t1, t2])
            await db.commit()

        async with self.Session() as db:
            await purge_customer(db, 1)
            await db.commit()

        async with self.Session() as db:
            self.assertIsNone(await db.get(Customer, 1))
            self.assertIsNotNone(await db.get(Customer, 2))
            self.assertIsNone(await db.get(Transaction, 10))
            self.assertIsNotNone(await db.get(Transaction, 11), "c2 的交易不应被误删")

    # ==================== purge_transaction ====================

    async def test_purge_transaction_cascades_related(self):
        """purge_transaction 级联删除：售后/返利/质保延长 + 交易本体。"""
        async with self.Session() as db:
            ids = await self._seed_full_chain(db)

        async with self.Session() as db:
            await purge_transaction(db, ids["transaction_id"])
            await db.commit()

        async with self.Session() as db:
            self.assertIsNone(await db.get(Transaction, ids["transaction_id"]))
            self.assertEqual(await self._count(db, AfterSales), 0)
            self.assertEqual(await self._count(db, RebateRecord), 0)
            self.assertEqual(await self._count(db, WarrantyExtension), 0)
            # 客户本体保留（purge_transaction 只处理交易分支）
            self.assertIsNotNone(await db.get(Customer, ids["customer_id"]))
            # 推荐关系不归 purge_transaction 管（由 purge_customer 处理）
            self.assertEqual(await self._count(db, CustomerLink), 1)

    async def test_purge_transaction_rejects_non_soft_deleted(self):
        """purge_transaction 拒绝未软删除的交易。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            db.add_all([
                Customer(id=1, xianyu_nickname="客户A"),
                Transaction(
                    id=10, customer_id=1, product_name="商品A",
                    sale_price=100.0, cost_price=50.0, profit=50.0,
                    trade_at=now, status="completed", warranty_days=30,
                    channel="xianyu",
                ),
            ])
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await purge_transaction(db, 10)
            self.assertIn("仅可彻底删除回收站", str(ctx.exception))

    async def test_purge_transaction_rejects_nonexistent(self):
        """purge_transaction 不存在的交易抛 ValueError。"""
        async with self.Session() as db:
            with self.assertRaises(ValueError):
                await purge_transaction(db, 99999)

    # ==================== purge_after_sales ====================

    async def test_purge_after_sales_only_deletes_self(self):
        """purge_after_sales 仅删工单本体（不级联到交易）。"""
        async with self.Session() as db:
            ids = await self._seed_full_chain(db)

        async with self.Session() as db:
            await purge_after_sales(db, ids["aftersales_id"])
            await db.commit()

        async with self.Session() as db:
            self.assertIsNone(await db.get(AfterSales, ids["aftersales_id"]))
            # 交易保留
            self.assertIsNotNone(await db.get(Transaction, ids["transaction_id"]))

    async def test_purge_after_sales_rejects_non_soft_deleted(self):
        """purge_after_sales 拒绝未软删除的工单。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            db.add_all([
                Customer(id=1, xianyu_nickname="客户A"),
                Transaction(
                    id=10, customer_id=1, product_name="商品A",
                    sale_price=100.0, cost_price=50.0, profit=50.0,
                    trade_at=now, status="completed", warranty_days=30,
                    channel="xianyu",
                ),
                AfterSales(
                    id=100, transaction_id=10, issue_desc="问题",
                    status="pending", attachments=[], created_at=now,
                ),
            ])
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await purge_after_sales(db, 100)
            self.assertIn("仅可彻底删除回收站", str(ctx.exception))

    # ==================== restore 校验 ====================

    async def test_restore_customer_rejects_non_soft_deleted(self):
        """restore_customer 拒绝未软删除的客户。"""
        async with self.Session() as db:
            c = Customer(id=1, xianyu_nickname="客户A")
            db.add(c)
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await restore_customer(db, 1)
            self.assertIn("未被删除", str(ctx.exception))

    async def test_restore_customer_rejects_nickname_conflict(self):
        """restore_customer 校验：昵称被在线客户占用时拒绝恢复。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            # 在线客户 c2 用了和已删除客户 c1 相同的昵称
            c1 = Customer(id=1, xianyu_nickname="重复昵称", deleted_at=now)
            c2 = Customer(id=2, xianyu_nickname="重复昵称")
            db.add_all([c1, c2])
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await restore_customer(db, 1)
            self.assertIn("已被其他客户占用", str(ctx.exception))

    async def test_restore_customer_succeeds_when_no_conflict(self):
        """restore_customer 成功路径：清 deleted_at + 触发 recalc。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            c1 = Customer(id=1, xianyu_nickname="可恢复客户", deleted_at=now)
            db.add(c1)
            await db.commit()

        async with self.Session() as db:
            await restore_customer(db, 1)
            await db.commit()

        async with self.Session() as db:
            c = await db.get(Customer, 1)
            self.assertIsNone(c.deleted_at)
            self.assertIsNotNone(c.updated_at)

    async def test_restore_transaction_rejects_when_customer_soft_deleted(self):
        """restore_transaction 校验：关联客户已被软删除时拒绝恢复。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            db.add_all([
                Customer(id=1, xianyu_nickname="客户A", deleted_at=now),
                Transaction(
                    id=10, customer_id=1, product_name="商品A",
                    sale_price=100.0, cost_price=50.0, profit=50.0,
                    trade_at=now, status="completed", warranty_days=30,
                    channel="xianyu", deleted_at=now,
                ),
            ])
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await restore_transaction(db, 10)
            self.assertIn("关联客户已被删除", str(ctx.exception))

    async def test_restore_after_sales_rejects_when_transaction_soft_deleted(self):
        """restore_after_sales 校验：关联交易被软删除时拒绝恢复。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            db.add_all([
                Customer(id=1, xianyu_nickname="客户A"),
                Transaction(
                    id=10, customer_id=1, product_name="商品A",
                    sale_price=100.0, cost_price=50.0, profit=50.0,
                    trade_at=now, status="completed", warranty_days=30,
                    channel="xianyu", deleted_at=now,
                ),
                AfterSales(
                    id=100, transaction_id=10, issue_desc="问题",
                    status="pending", attachments=[],
                    deleted_at=now, created_at=now,
                ),
            ])
            await db.commit()

        async with self.Session() as db:
            with self.assertRaises(ValueError) as ctx:
                await restore_after_sales(db, 100)
            self.assertIn("关联交易已被删除", str(ctx.exception))

    async def test_restore_transaction_succeeds_when_customer_alive(self):
        """restore_transaction 成功路径。"""
        now = datetime(2026, 7, 1)
        async with self.Session() as db:
            db.add_all([
                Customer(id=1, xianyu_nickname="客户A"),
                Transaction(
                    id=10, customer_id=1, product_name="商品A",
                    sale_price=100.0, cost_price=50.0, profit=50.0,
                    trade_at=now, status="completed", warranty_days=30,
                    channel="xianyu", deleted_at=now,
                ),
            ])
            await db.commit()

        async with self.Session() as db:
            await restore_transaction(db, 10)
            await db.commit()

        async with self.Session() as db:
            t = await db.get(Transaction, 10)
            self.assertIsNone(t.deleted_at)


if __name__ == "__main__":
    unittest.main()
