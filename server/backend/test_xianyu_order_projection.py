import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, ProductTemplate, Transaction, XianyuAccount, XianyuOrder
from app.services.xianyu import order_service


def make_completed_order(
    order_no: str = "ORDER-1",
    item_id: str | None = None,
    shipped_at: str | None = None,
) -> dict:
    item = {"title": "product-a"}
    if item_id:
        item["itemId"] = item_id
    order = {
        "commonData": {
            "orderId": order_no,
            "orderStatus": "TRADE_FINISHED",
            "finishTime": "2026-07-01T12:34:56",
        },
        "buyerInfoVO": {"userNick": "buyer-a"},
        "itemVO": item,
        "priceVO": {"confirmFee": "88.00"},
    }
    if shipped_at:
        order["commonData"]["consignTime"] = shipped_at
    return order


def make_order_with_status(order_no: str, order_status: str) -> dict:
    order = make_completed_order(order_no)
    order["commonData"]["orderStatus"] = order_status
    return order


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

    async def test_sync_projects_pay_to_receiving_statuses_as_pending_transactions(self):
        cases = [
            ("ORDER-PAID", "已付款", "pending"),
            ("ORDER-WAIT-SHIP", "待发货", "pending"),
            ("ORDER-SHIPPED", "已发货", "pending"),
            ("ORDER-WAIT-RECEIVE", "待收货", "pending"),
            ("ORDER-REFUNDING", "退款处理中", "aftersales"),
        ]
        async with self.Session() as db:
            account = await self._create_account(db)

            result = await self._sync_orders(
                db,
                account.id,
                [make_order_with_status(order_no, status) for order_no, status, _ in cases],
            )

            txs = {
                tx.xianyu_order_no: tx
                for tx in (
                    await db.execute(
                        select(Transaction).where(Transaction.xianyu_order_no.in_([case[0] for case in cases]))
                    )
                ).scalars().all()
            }
            mirrors = {
                mirror.order_no: mirror
                for mirror in (
                    await db.execute(
                        select(XianyuOrder).where(XianyuOrder.order_no.in_([case[0] for case in cases]))
                    )
                ).scalars().all()
            }

        self.assertEqual(result["created_count"], len(cases))
        for order_no, _platform_status, expected_status in cases:
            with self.subTest(order_no=order_no):
                self.assertIn(order_no, txs)
                self.assertEqual(txs[order_no].status, expected_status)
                self.assertEqual(mirrors[order_no].projected_transaction_id, txs[order_no].id)

    async def test_sync_updates_existing_projection_without_creating_duplicate_transaction(self):
        async with self.Session() as db:
            account = await self._create_account(db)

            first = await self._sync_orders(
                db,
                account.id,
                [make_order_with_status("ORDER-LIFECYCLE", "待发货")],
            )
            second = await self._sync_orders(
                db,
                account.id,
                [make_order_with_status("ORDER-LIFECYCLE", "待收货")],
            )

            txs = list(
                (
                    await db.execute(
                        select(Transaction).where(Transaction.xianyu_order_no == "ORDER-LIFECYCLE")
                    )
                ).scalars().all()
            )
            mirror = await db.scalar(
                select(XianyuOrder).where(XianyuOrder.order_no == "ORDER-LIFECYCLE")
            )

        self.assertEqual(first["created_count"], 1)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["skipped_count"], 1)
        self.assertEqual(len(txs), 1)
        self.assertIsNotNone(mirror)
        self.assertEqual(mirror.order_status, "待收货")
        self.assertEqual(mirror.projected_transaction_id, txs[0].id)

    async def test_sync_uses_imported_item_template_when_order_has_item_id(self):
        async with self.Session() as db:
            account = await self._create_account(db)
            template = ProductTemplate(
                name="账号A商品模板",
                default_cost=12.5,
                default_sale_price=88,
                category="闲鱼导入",
                warranty_days=90,
                is_active=True,
                source_xianyu_account_id=account.id,
                source_xianyu_item_id="ITEM-1",
            )
            db.add(template)
            await db.flush()

            result = await self._sync_orders(
                db,
                account.id,
                [make_completed_order(item_id="ITEM-1")],
            )

            tx = await db.scalar(
                select(Transaction).where(Transaction.xianyu_order_no == "ORDER-1")
            )

        self.assertEqual(result["created_count"], 1)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.product_template_id, template.id)
        self.assertEqual(tx.cost_price, 12.5)
        self.assertEqual(tx.profit, 75.5)
        self.assertEqual(tx.warranty_days, 90)

    async def test_sync_uses_shipment_time_as_warranty_start(self):
        async with self.Session() as db:
            account = await self._create_account(db)

            result = await self._sync_orders(
                db,
                account.id,
                [
                    make_completed_order(
                        shipped_at="2026-07-03T09:30:00",
                    )
                ],
            )

            tx = await db.scalar(
                select(Transaction).where(Transaction.xianyu_order_no == "ORDER-1")
            )

        self.assertEqual(result["created_count"], 1)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.shipped_at, datetime(2026, 7, 3, 9, 30, 0))
        self.assertEqual(tx.warranty_end, datetime(2026, 8, 2, 9, 30, 0))


if __name__ == "__main__":
    unittest.main()
