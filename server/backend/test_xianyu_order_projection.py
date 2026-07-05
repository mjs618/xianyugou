import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, Transaction, XianyuAccount, XianyuOrder
from app.services.xianyu import order_service


def make_completed_order(order_no: str = "ORDER-1") -> dict:
    return {
        "commonData": {
            "orderId": order_no,
            "orderStatus": "TRADE_FINISHED",
            "finishTime": "2026-07-01T12:34:56",
        },
        "buyerInfoVO": {"userNick": "buyer-a"},
        "itemVO": {"title": "product-a"},
        "priceVO": {"confirmFee": "88.00"},
    }


def make_closed_order(order_no: str = "ORDER-1") -> dict:
    order = make_completed_order(order_no)
    order["commonData"]["orderStatus"] = "CLOSED"
    return order


class FakeMtop:
    cookies_changed = False
    cookie_str = "plain-cookie"

    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str


class XianyuOrderProjectionTests(unittest.IsolatedAsyncioTestCase):
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

    async def _create_account(self, db):
        account = XianyuAccount(nickname="safe-account", cookies="encrypted-cookie")
        db.add(account)
        await db.flush()
        return account

    async def _sync_orders(self, db, account_id: int, orders: list[dict]):
        async def fake_fetch_orders(mtop, *, max_pages):
            return orders

        with (
            patch.object(order_service, "get_plain_cookies", return_value="plain-cookie"),
            patch.object(order_service, "MtopClient", FakeMtop),
            patch.object(order_service, "fetch_orders", fake_fetch_orders),
        ):
            return await order_service.sync_orders_for_account(db, account_id)

    async def test_sync_records_created_transaction_id_on_order_mirror(self):
        async with self.Session() as db:
            account = await self._create_account(db)

            result = await self._sync_orders(db, account.id, [make_completed_order()])

            mirror = await db.scalar(
                select(XianyuOrder).where(XianyuOrder.order_no == "ORDER-1")
            )
            tx = await db.scalar(
                select(Transaction).where(Transaction.xianyu_order_no == "ORDER-1")
            )

        self.assertEqual(result["created_count"], 1)
        self.assertIsNotNone(mirror)
        self.assertIsNotNone(tx)
        self.assertEqual(mirror.projected_transaction_id, tx.id)

    async def test_sync_backfills_existing_transaction_id_on_order_mirror(self):
        async with self.Session() as db:
            account = await self._create_account(db)
            customer = Customer(xianyu_nickname="buyer-a")
            db.add(customer)
            await db.flush()
            tx = Transaction(
                customer_id=customer.id,
                xianyu_order_no="ORDER-1",
                product_name="product-a",
                sale_price=88.0,
                cost_price=0.0,
                profit=88.0,
                trade_at=datetime(2026, 7, 1, 12, 34, 56),
                status="completed",
                warranty_days=30,
                source_type="direct",
                attachments=[],
            )
            db.add(tx)
            await db.flush()

            result = await self._sync_orders(db, account.id, [make_completed_order()])

            mirror = await db.scalar(
                select(XianyuOrder).where(XianyuOrder.order_no == "ORDER-1")
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertIsNotNone(mirror)
        self.assertEqual(mirror.projected_transaction_id, tx.id)

    async def test_sync_backfills_existing_transaction_id_before_status_filter(self):
        async with self.Session() as db:
            account = await self._create_account(db)
            customer = Customer(xianyu_nickname="buyer-a")
            db.add(customer)
            await db.flush()
            tx = Transaction(
                customer_id=customer.id,
                xianyu_order_no="ORDER-1",
                product_name="product-a",
                sale_price=88.0,
                cost_price=0.0,
                profit=88.0,
                trade_at=datetime(2026, 7, 1, 12, 34, 56),
                status="completed",
                warranty_days=30,
                source_type="direct",
                attachments=[],
            )
            db.add(tx)
            await db.flush()

            result = await self._sync_orders(db, account.id, [make_closed_order()])

            mirror = await db.scalar(
                select(XianyuOrder).where(XianyuOrder.order_no == "ORDER-1")
            )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertIsNotNone(mirror)
        self.assertEqual(mirror.projected_transaction_id, tx.id)


if __name__ == "__main__":
    unittest.main()
