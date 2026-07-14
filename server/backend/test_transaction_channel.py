"""销售渠道（channel）相关测试。

验证：
1. create_transaction 正确落库 channel 字段（含默认值）
2. update_transaction 可更新 channel
3. 财务聚合按 channel 过滤
4. get_channel_breakdown GROUP BY channel 聚合正确
"""
import unittest
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, Transaction
from app.services.transaction_service import create_transaction, list_transactions, update_transaction
from app.services.finance_service import (
    get_channel_breakdown,
    get_finance_overview_by_range,
)


class TransactionChannelTests(unittest.IsolatedAsyncioTestCase):
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

    async def _create_customer(self, db, nickname="buyer-a"):
        customer = Customer(xianyu_nickname=nickname)
        db.add(customer)
        await db.flush()
        return customer

    async def test_create_transaction_with_channel(self):
        """创建交易时 channel 字段正确落库，默认值为 xianyu。"""
        async with self.Session() as db:
            customer = await self._create_customer(db)

            # 显式传 channel=wechat
            tx_wechat = await create_transaction(
                db,
                customer_id=customer.id,
                product_name="wechat-product",
                sale_price=100,
                cost_price=20,
                trade_at=datetime(2026, 7, 1, 10, 0, 0),
                status="completed",
                channel="wechat",
            )
            await db.flush()

            # 不传 channel，默认 xianyu
            tx_default = await create_transaction(
                db,
                customer_id=customer.id,
                product_name="xianyu-product",
                sale_price=200,
                cost_price=50,
                trade_at=datetime(2026, 7, 2, 10, 0, 0),
                status="completed",
            )
            await db.flush()

        self.assertEqual(tx_wechat.channel, "wechat")
        self.assertEqual(tx_default.channel, "xianyu")

    async def test_update_transaction_channel(self):
        """update_transaction 可更新 channel 字段。"""
        async with self.Session() as db:
            customer = await self._create_customer(db)
            tx = await create_transaction(
                db,
                customer_id=customer.id,
                product_name="product-a",
                sale_price=100,
                cost_price=20,
                trade_at=datetime(2026, 7, 1, 10, 0, 0),
                status="completed",
                channel="xianyu",
            )
            await db.flush()

            updated = await update_transaction(db, tx.id, {"channel": "wechat"})
            await db.flush()

        self.assertEqual(updated.channel, "wechat")

    async def test_finance_aggregation_channel_filter(self):
        """财务聚合按 channel 过滤：只统计指定渠道交易。"""
        start = datetime(2026, 7, 1, 0, 0, 0)
        end = datetime(2026, 7, 31, 23, 59, 59)
        async with self.Session() as db:
            customer = await self._create_customer(db)

            # 闲鱼渠道：售价 200，成本 100，利润 100
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="xianyu-item",
                sale_price=200,
                cost_price=100,
                trade_at=datetime(2026, 7, 5, 10, 0, 0),
                status="completed",
                channel="xianyu",
            )
            # 微信渠道：售价 300，成本 150，利润 150
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="wechat-item",
                sale_price=300,
                cost_price=150,
                trade_at=datetime(2026, 7, 10, 10, 0, 0),
                status="completed",
                channel="wechat",
            )
            await db.flush()

            # 按 channel=wechat 过滤 → 只算微信那笔
            wechat_ov = await get_finance_overview_by_range(db, start, end, channel="wechat")
            # 不过滤 → 算两笔
            all_ov = await get_finance_overview_by_range(db, start, end)

        # 微信过滤：income=300, cost=150, profit=150, count=1
        self.assertEqual(wechat_ov["totalIncome"], 300)
        self.assertEqual(wechat_ov["totalCost"], 150)
        self.assertEqual(wechat_ov["totalProfit"], 150)
        self.assertEqual(wechat_ov["tradeCount"], 1)

        # 全部：income=500, count=2
        self.assertEqual(all_ov["totalIncome"], 500)
        self.assertEqual(all_ov["tradeCount"], 2)

    async def test_channel_breakdown(self):
        """get_channel_breakdown 按 channel GROUP BY 聚合，返回各渠道收入/成本/利润/笔数。"""
        start = datetime(2026, 7, 1, 0, 0, 0)
        end = datetime(2026, 7, 31, 23, 59, 59)
        async with self.Session() as db:
            customer = await self._create_customer(db)

            # 闲鱼：售价 200，成本 100
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="xianyu-item",
                sale_price=200,
                cost_price=100,
                trade_at=datetime(2026, 7, 5, 10, 0, 0),
                status="completed",
                channel="xianyu",
            )
            # 微信：售价 300，成本 150
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="wechat-item",
                sale_price=300,
                cost_price=150,
                trade_at=datetime(2026, 7, 10, 10, 0, 0),
                status="completed",
                channel="wechat",
            )
            await db.flush()

            rows = await get_channel_breakdown(db, start, end)

        # 按渠道分组
        by_channel = {r["channel"]: r for r in rows}
        self.assertIn("xianyu", by_channel)
        self.assertIn("wechat", by_channel)

        xy = by_channel["xianyu"]
        self.assertEqual(xy["income"], 200)
        self.assertEqual(xy["cost"], 100)
        self.assertEqual(xy["profit"], 100)
        self.assertEqual(xy["count"], 1)

        wc = by_channel["wechat"]
        self.assertEqual(wc["income"], 300)
        self.assertEqual(wc["cost"], 150)
        self.assertEqual(wc["profit"], 150)
        self.assertEqual(wc["count"], 1)

    async def test_list_transactions_filter_by_channel(self):
        """list_transactions 支持 channel 过滤参数，只返回指定渠道交易。"""
        async with self.Session() as db:
            customer = await self._create_customer(db)
            # 闲鱼渠道
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="xianyu-item",
                sale_price=200,
                cost_price=100,
                trade_at=datetime(2026, 7, 5, 10, 0, 0),
                status="completed",
                channel="xianyu",
            )
            # 微信渠道
            await create_transaction(
                db,
                customer_id=customer.id,
                product_name="wechat-item",
                sale_price=300,
                cost_price=150,
                trade_at=datetime(2026, 7, 10, 10, 0, 0),
                status="completed",
                channel="wechat",
            )
            await db.flush()

            # channel=wechat → 只返回微信那笔
            wechat_txs = await list_transactions(db, channel="wechat")
            # 不过滤 → 返回两笔
            all_txs = await list_transactions(db)

        self.assertEqual(len(wechat_txs), 1)
        self.assertEqual(wechat_txs[0].channel, "wechat")
        self.assertEqual(wechat_txs[0].product_name, "wechat-item")
        self.assertEqual(len(all_txs), 2)


if __name__ == "__main__":
    unittest.main()
