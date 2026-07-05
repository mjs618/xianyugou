import unittest
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import XianyuAccount, XianyuOrder
from app.services.xianyu.order_service import upsert_order_mirror


class XianyuOrderMirrorTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_upsert_order_mirror_is_idempotent_per_account_order(self):
        async with self.Session() as db:
            account = XianyuAccount(nickname="safe-account", cookies="encrypted-cookie")
            db.add(account)
            await db.flush()

            first = await upsert_order_mirror(
                db,
                account.id,
                {
                    "commonData": {
                        "orderId": "ORDER-1",
                        "orderStatus": "TRADE_FINISHED",
                        "finishTime": "2026-07-01T12:34:56",
                    },
                    "buyerInfoVO": {"userNick": "buyer-a"},
                    "itemVO": {"title": "product-a"},
                    "priceVO": {"confirmFee": "88.00"},
                },
            )
            second = await upsert_order_mirror(
                db,
                account.id,
                {
                    "commonData": {
                        "orderId": "ORDER-1",
                        "orderStatus": "CLOSED",
                        "finishTime": "2026-07-02T12:34:56",
                    },
                    "buyerInfoVO": {"userNick": "buyer-b"},
                    "itemVO": {"title": "product-b"},
                    "priceVO": {"confirmFee": "99.00"},
                },
            )

            count = await db.scalar(select(func.count(XianyuOrder.id)))

        self.assertEqual(first.id, second.id)
        self.assertEqual(count, 1)
        self.assertEqual(second.account_id, account.id)
        self.assertEqual(second.order_no, "ORDER-1")
        self.assertEqual(second.order_status, "CLOSED")
        self.assertEqual(second.buyer_nick, "buyer-b")
        self.assertEqual(second.product_name, "product-b")
        self.assertEqual(second.sale_price, 99.0)
        self.assertEqual(second.trade_at, datetime(2026, 7, 2, 12, 34, 56))
        self.assertEqual(second.raw_order["itemVO"]["title"], "product-b")


if __name__ == "__main__":
    unittest.main()
