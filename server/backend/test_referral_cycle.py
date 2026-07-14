"""D3 测试补充：referral_service._would_create_cycle 循环引用检测。

验证：
1. referrer 无父链：不会成环
2. buyer 是 referrer 的直接父节点：会成环
3. buyer 是 referrer 的祖父节点：会成环
4. buyer 与 referrer 父链无关：不会成环
5. 自引用 referrer == buyer：会成环
6. 父链中存在环（数据异常）：不死循环，正常返回
7. _calc_referral_level 层级计算
"""
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, CustomerLink, Transaction
from app.services.referral_service import (
    _calc_referral_level,
    _would_create_cycle,
)


class ReferralCycleTests(unittest.IsolatedAsyncioTestCase):
    """推荐链循环引用检测。"""

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

    async def _create_customer(self, db, nickname: str, customer_id: int) -> Customer:
        """创建客户并指定 id（测试用）。"""
        c = Customer(id=customer_id, xianyu_nickname=nickname)
        db.add(c)
        await db.flush()
        return c

    async def _create_link(
        self, db, referrer_id: int, buyer_id: int, transaction_id: int, level: int = 1
    ) -> CustomerLink:
        """创建推荐关系。"""
        link = CustomerLink(
            referrer_id=referrer_id,
            buyer_id=buyer_id,
            transaction_id=transaction_id,
            level=level,
        )
        db.add(link)
        await db.flush()
        return link

    async def _setup_customers_and_transactions(self, db, ids: list[int]) -> dict[int, int]:
        """批量创建客户和交易，返回 {customer_id: transaction_id}。"""
        tx_map: dict[int, int] = {}
        for cid in ids:
            await self._create_customer(db, f"客户{cid}", cid)
            tx = Transaction(
                customer_id=cid,
                product_name=f"商品{cid}",
                sale_price=100.0,
                cost_price=80.0,
                profit=20.0,
                trade_at=__import__("datetime").datetime(2026, 7, 1),
                status="completed",
                warranty_days=0,
                source_type="direct",
                channel="xianyu",
                attachments=[],
            )
            db.add(tx)
            await db.flush()
            tx_map[cid] = tx.id
        return tx_map

    async def test_no_parent_chain_no_cycle(self):
        """referrer 没有父链且 buyer 与 referrer 不同：不会成环。

        语义：_would_create_cycle(referrer, buyer) 检测"建立 referrer→buyer 关系"是否成环。
        算法：从 referrer 向上遍历父链，若途中遇到 buyer_id 则成环（buyer 是 referrer 祖先）。
        """
        async with self.Session() as db:
            # 链：1 → 2（1 推荐 2，1 是 2 的父）
            tx_map = await self._setup_customers_and_transactions(db, [1, 2, 3, 4])
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1])
            await db.commit()

        async with self.Session() as db:
            # referrer=3（无父链），buyer=4：3 的父链为空，4 不在链中 → 不会成环
            result = await _would_create_cycle(db, referrer_id=3, buyer_id=4)
            self.assertFalse(result)

    async def test_buyer_is_direct_parent_creates_cycle(self):
        """buyer 是 referrer 的直接父节点：会成环。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2])
            # 1 → 2（1 是 2 的父）
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1])
            await db.commit()

        async with self.Session() as db:
            # referrer=2（父是 1），buyer=1：2→1→1，1==1 成环
            result = await _would_create_cycle(db, referrer_id=2, buyer_id=1)
            self.assertTrue(result)

    async def test_buyer_is_grandparent_creates_cycle(self):
        """buyer 是 referrer 的祖父节点：会成环。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2, 3])
            # 1 → 2，2 → 3（1 是 3 的祖父）
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1], level=1)
            await self._create_link(db, referrer_id=2, buyer_id=3, transaction_id=tx_map[2], level=2)
            await db.commit()

        async with self.Session() as db:
            # referrer=3（父是 2，祖父是 1），buyer=1：3→2→1，1==1 成环
            result = await _would_create_cycle(db, referrer_id=3, buyer_id=1)
            self.assertTrue(result)

    async def test_buyer_unrelated_no_cycle(self):
        """buyer 与 referrer 父链无关：不会成环。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2, 3, 4])
            # 1 → 2，3 → 4（两条独立链）
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1])
            await self._create_link(db, referrer_id=3, buyer_id=4, transaction_id=tx_map[3])
            await db.commit()

        async with self.Session() as db:
            # referrer=2（父是 1），buyer=3：2→1→None，3 不在链中
            result = await _would_create_cycle(db, referrer_id=2, buyer_id=3)
            self.assertFalse(result)

    async def test_self_reference_creates_cycle(self):
        """自引用 referrer == buyer：第一次迭代即返回 True。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1])
            await db.commit()

        async with self.Session() as db:
            result = await _would_create_cycle(db, referrer_id=1, buyer_id=1)
            self.assertTrue(result)

    async def test_circular_parent_chain_does_not_hang(self):
        """父链本身存在环（数据异常）：不死循环，正常返回。

        构造异常数据：1→2，2→1（互相推荐），然后查 referrer=2, buyer=3
        应在 visited 集合触发后退出，不死循环。
        """
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2, 3])
            # 异常数据：1→2 和 2→1（形成环）
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1], level=1)
            await self._create_link(db, referrer_id=2, buyer_id=1, transaction_id=tx_map[2], level=1)
            await db.commit()

        async with self.Session() as db:
            # referrer=1（父链 1→2→1→...，环），buyer=3：visited 集合防止死循环
            result = await _would_create_cycle(db, referrer_id=1, buyer_id=3)
            self.assertFalse(result)

    async def test_calc_referral_level_root(self):
        """根节点（无父）level = 0。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2])
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1], level=1)
            await db.commit()

        async with self.Session() as db:
            level = await _calc_referral_level(db, buyer_id=1)
            self.assertEqual(level, 0)

    async def test_calc_referral_level_one_deep(self):
        """一阶推荐：level = 1。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2])
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1], level=1)
            await db.commit()

        async with self.Session() as db:
            level = await _calc_referral_level(db, buyer_id=2)
            self.assertEqual(level, 1)

    async def test_calc_referral_level_two_deep(self):
        """二阶推荐：level = 2。"""
        async with self.Session() as db:
            tx_map = await self._setup_customers_and_transactions(db, [1, 2, 3])
            await self._create_link(db, referrer_id=1, buyer_id=2, transaction_id=tx_map[1], level=1)
            await self._create_link(db, referrer_id=2, buyer_id=3, transaction_id=tx_map[2], level=2)
            await db.commit()

        async with self.Session() as db:
            level = await _calc_referral_level(db, buyer_id=3)
            self.assertEqual(level, 2)


if __name__ == "__main__":
    unittest.main()
