from datetime import datetime, timedelta
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import OperatingExpense, Transaction
from app.services import finance_service


class ExpenseFinanceServiceTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_overview_counts_operating_expense_as_cost(self):
        async with self.Session() as db:
            db.add(Transaction(
                customer_id=1,
                product_name="商品A",
                sale_price=100,
                cost_price=30,
                profit=70,
                trade_at=datetime(2026, 7, 9, 10, 0, 0),
                status="completed",
            ))
            db.add(OperatingExpense(
                category="擦亮",
                amount=6,
                occurred_at=datetime(2026, 7, 9, 11, 0, 0),
            ))
            await db.commit()

            overview = await finance_service.get_finance_overview_by_range(
                db,
                datetime(2026, 7, 1),
                datetime(2026, 7, 31, 23, 59, 59),
            )

        self.assertEqual(overview["totalIncome"], 100)
        self.assertEqual(overview["operatingExpense"], 6)
        self.assertEqual(overview["totalCost"], 36)
        self.assertEqual(overview["totalProfit"], 64)

    async def test_trend_and_monthly_comparison_subtract_operating_expense(self):
        async with self.Session() as db:
            day = datetime.utcnow() - timedelta(minutes=1)
            db.add(Transaction(
                customer_id=1,
                product_name="商品A",
                sale_price=100,
                cost_price=30,
                profit=70,
                trade_at=day,
                status="completed",
            ))
            db.add(OperatingExpense(
                category="擦亮",
                amount=6,
                occurred_at=day,
            ))
            await db.commit()

            trend = await finance_service.get_trend(db, 1)
            monthly = await finance_service.get_monthly_comparison(db, 1)

        self.assertEqual(trend[-1]["cost"], 36)
        self.assertEqual(trend[-1]["profit"], 64)
        self.assertEqual(monthly[-1]["cost"], 36)
        self.assertEqual(monthly[-1]["profit"], 64)


if __name__ == "__main__":
    unittest.main()
