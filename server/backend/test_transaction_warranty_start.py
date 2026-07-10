import unittest
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer
from app.services.transaction_service import create_transaction


class TransactionWarrantyStartTests(unittest.IsolatedAsyncioTestCase):
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

    async def _create_customer(self, db):
        customer = Customer(xianyu_nickname="buyer-a")
        db.add(customer)
        await db.flush()
        return customer

    async def test_completed_transaction_warranty_starts_from_shipment_time(self):
        async with self.Session() as db:
            customer = await self._create_customer(db)

            tx = await create_transaction(
                db,
                customer_id=customer.id,
                product_name="product-a",
                sale_price=100,
                cost_price=20,
                trade_at=datetime(2026, 7, 1, 10, 0, 0),
                shipped_at=datetime(2026, 7, 3, 9, 30, 0),
                status="completed",
                warranty_days=30,
            )

        self.assertEqual(tx.shipped_at, datetime(2026, 7, 3, 9, 30, 0))
        self.assertEqual(tx.warranty_end, datetime(2026, 8, 2, 9, 30, 0))

    async def test_completed_transaction_with_zero_warranty_has_no_warranty_end(self):
        async with self.Session() as db:
            customer = await self._create_customer(db)

            tx = await create_transaction(
                db,
                customer_id=customer.id,
                product_name="product-a",
                sale_price=100,
                cost_price=20,
                trade_at=datetime(2026, 7, 1, 10, 0, 0),
                shipped_at=datetime(2026, 7, 3, 9, 30, 0),
                status="completed",
                warranty_days=0,
            )

        self.assertEqual(tx.warranty_days, 0)
        self.assertIsNone(tx.warranty_end)


if __name__ == "__main__":
    unittest.main()
