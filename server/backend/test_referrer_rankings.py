"""E4/E5 测试：get_referrer_rankings SQL GROUP BY 重写后的语义验证。

验证改写后行为：
1. 空数据库返回 []
2. 单个 referrer + 单个 buyer → introducedCount=1, broughtRevenue=buyer成交额
3. 多个 buyer → introducedCount=不同 buyer 数量
4. 多个 referrer → 按 broughtRevenue 倒序
5. 软删除客户 → 昵称显示 "客户{id}"
6. closed 状态交易不计入（与 project memory 一致；原实现遗漏，新实现修复）
7. paid/pending 返利汇总
8. 多个 buyer 共享同一 referrer，收入累加
"""
import unittest
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, CustomerLink, RebateRecord, Transaction
from app.services.referral_service import get_referrer_rankings


class GetReferrerRankingsTests(unittest.IsolatedAsyncioTestCase):
    """get_referrer_rankings SQL 重写后的语义验证。"""

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

    async def _add_customer(self, db, *, customer_id: int, nickname: str, deleted: bool = False) -> Customer:
        c = Customer(
            id=customer_id,
            xianyu_nickname=nickname,
            deleted_at=datetime(2026, 7, 1) if deleted else None,
        )
        db.add(c)
        await db.flush()
        return c

    async def _add_link(self, db, *, referrer_id: int, buyer_id: int, transaction_id: int = 1) -> CustomerLink:
        link = CustomerLink(
            referrer_id=referrer_id,
            buyer_id=buyer_id,
            transaction_id=transaction_id,
            level=0,
        )
        db.add(link)
        await db.flush()
        return link

    async def _add_transaction(
        self, db, *, tx_id: int, customer_id: int, sale_price: float,
        status: str = "completed", deleted: bool = False,
    ) -> Transaction:
        tx = Transaction(
            id=tx_id,
            customer_id=customer_id,
            product_name="测试商品",
            sale_price=sale_price,
            cost_price=0.0,
            profit=sale_price,
            trade_at=datetime(2026, 7, 1, 10, 0, 0),
            status=status,
            warranty_days=0,
            channel="xianyu",
            deleted_at=datetime(2026, 7, 1) if deleted else None,
        )
        db.add(tx)
        await db.flush()
        return tx

    async def _add_rebate(self, db, *, rebate_id: int, referrer_id: int, buyer_id: int,
                          amount: float, status: str, transaction_id: int = 1) -> RebateRecord:
        r = RebateRecord(
            id=rebate_id,
            referrer_id=referrer_id,
            buyer_id=buyer_id,
            transaction_id=transaction_id,
            amount=amount,
            rate=0.1,
            status=status,
        )
        db.add(r)
        await db.flush()
        return r

    # ==================== 基础场景 ====================

    async def test_empty_db_returns_empty_list(self):
        """空数据库返回空列表。"""
        async with self.Session() as db:
            result = await get_referrer_rankings(db)
        self.assertEqual(result, [])

    async def test_single_referrer_single_buyer(self):
        """单 referrer + 单 buyer：推荐人数=1，收入=buyer 成交额。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["referrerId"], 1)
        self.assertEqual(entry["nickname"], "推荐人A")
        self.assertEqual(entry["introducedCount"], 1)
        self.assertEqual(entry["broughtRevenue"], 100.0)
        self.assertEqual(entry["paidRebate"], 0.0)
        self.assertEqual(entry["pendingRebate"], 0.0)

    async def test_multiple_buyers_under_one_referrer(self):
        """一个 referrer 多个 buyer：introducedCount=不同 buyer 数量，收入累加。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_customer(db, customer_id=3, nickname="买家C")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_link(db, referrer_id=1, buyer_id=3)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await self._add_transaction(db, tx_id=11, customer_id=3, sale_price=200.0)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["introducedCount"], 2)
        self.assertEqual(entry["broughtRevenue"], 300.0)

    async def test_multiple_referrers_sorted_by_revenue_desc(self):
        """多个 referrer 按 broughtRevenue 倒序。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="推荐人B")
            await self._add_customer(db, customer_id=10, nickname="买家1")
            await self._add_customer(db, customer_id=11, nickname="买家2")
            # A 推荐 买家1，收入 200
            await self._add_link(db, referrer_id=1, buyer_id=10)
            await self._add_transaction(db, tx_id=100, customer_id=10, sale_price=200.0)
            # B 推荐 买家2，收入 500
            await self._add_link(db, referrer_id=2, buyer_id=11)
            await self._add_transaction(db, tx_id=101, customer_id=11, sale_price=500.0)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(len(result), 2)
        # B 收入高，排前面
        self.assertEqual(result[0]["referrerId"], 2)
        self.assertEqual(result[0]["broughtRevenue"], 500.0)
        self.assertEqual(result[1]["referrerId"], 1)
        self.assertEqual(result[1]["broughtRevenue"], 200.0)

    # ==================== 过滤规则 ====================

    async def test_closed_transactions_excluded_from_revenue(self):
        """status='closed' 交易不计入收入（与 project memory 规则一致）。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            # 一笔正常交易 + 一笔 closed 交易
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0, status="completed")
            await self._add_transaction(db, tx_id=11, customer_id=2, sale_price=999.0, status="closed")
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(result[0]["broughtRevenue"], 100.0, "closed 交易不应计入收入")

    async def test_deleted_transactions_excluded_from_revenue(self):
        """软删除交易不计入收入。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await self._add_transaction(db, tx_id=11, customer_id=2, sale_price=500.0, deleted=True)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(result[0]["broughtRevenue"], 100.0, "软删除交易不应计入收入")

    async def test_soft_deleted_referrer_shows_fallback_nickname(self):
        """软删除 referrer 显示 "客户{id}" 而非昵称。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="已删除推荐人", deleted=True)
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(result[0]["nickname"], "客户1")

    # ==================== 返利汇总 ====================

    async def test_paid_and_pending_rebates_aggregated(self):
        """paid 和 pending 状态返利分别汇总。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_customer(db, customer_id=3, nickname="买家C")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_link(db, referrer_id=1, buyer_id=3)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await self._add_transaction(db, tx_id=11, customer_id=3, sale_price=200.0)
            # 1 笔 paid + 2 笔 pending
            await self._add_rebate(db, rebate_id=1000, referrer_id=1, buyer_id=2, amount=5.0, status="paid")
            await self._add_rebate(db, rebate_id=1001, referrer_id=1, buyer_id=3, amount=10.0, status="pending")
            await self._add_rebate(db, rebate_id=1002, referrer_id=1, buyer_id=3, amount=8.0, status="pending")
            await db.commit()

            result = await get_referrer_rankings(db)

        entry = result[0]
        self.assertEqual(entry["paidRebate"], 5.0)
        self.assertEqual(entry["pendingRebate"], 18.0)

    async def test_cancelled_rebates_excluded(self):
        """cancelled 状态返利不汇总。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await self._add_rebate(db, rebate_id=1000, referrer_id=1, buyer_id=2, amount=5.0, status="paid")
            await self._add_rebate(db, rebate_id=1001, referrer_id=1, buyer_id=2, amount=99.0, status="cancelled")
            await db.commit()

            result = await get_referrer_rankings(db)

        entry = result[0]
        self.assertEqual(entry["paidRebate"], 5.0, "cancelled 不应计入")
        self.assertEqual(entry["pendingRebate"], 0.0)

    # ==================== 边界场景 ====================

    async def test_referrer_with_only_rebates_no_links(self):
        """referrer 有返利但无推荐关系：仍出现在列表中（按返利汇总）。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_rebate(db, rebate_id=1000, referrer_id=1, buyer_id=2, amount=10.0, status="paid")
            await db.commit()

            result = await get_referrer_rankings(db)

        # 应有一条记录
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["referrerId"], 1)
        self.assertEqual(entry["introducedCount"], 0)
        self.assertEqual(entry["paidRebate"], 10.0)

    async def test_buyer_with_no_transactions(self):
        """buyer 无交易：referrer 仍出现在列表中，但 broughtRevenue=0。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await db.commit()

            result = await get_referrer_rankings(db)

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["introducedCount"], 1)
        self.assertEqual(entry["broughtRevenue"], 0.0)

    async def test_duplicate_buyer_links_counted_once(self):
        """同一 referrer→buyer 多次推荐：introducedCount 只算 1 次。"""
        async with self.Session() as db:
            await self._add_customer(db, customer_id=1, nickname="推荐人A")
            await self._add_customer(db, customer_id=2, nickname="买家B")
            # 两条相同的 link（不同 transaction_id）
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_link(db, referrer_id=1, buyer_id=2)
            await self._add_transaction(db, tx_id=10, customer_id=2, sale_price=100.0)
            await db.commit()

            result = await get_referrer_rankings(db)

        entry = result[0]
        self.assertEqual(entry["introducedCount"], 1, "去重后只算 1 个 buyer")


if __name__ == "__main__":
    unittest.main()
