import unittest
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import AfterSales, Customer, NotificationRecord, Transaction
from app.services import notification_service


class NotificationServiceTests(unittest.IsolatedAsyncioTestCase):
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

    async def _create_ticket(self, db, *, status: str, created_at: datetime):
        customer = Customer(xianyu_nickname="买家A")
        db.add(customer)
        await db.flush()
        tx = Transaction(
            customer_id=customer.id,
            product_name="测试商品",
            sale_price=100,
            cost_price=20,
            profit=80,
            trade_at=datetime(2026, 7, 1, 10, 0, 0),
            status="aftersales",
            warranty_days=30,
            source_type="direct",
            attachments=[],
        )
        db.add(tx)
        await db.flush()
        ticket = AfterSales(
            transaction_id=tx.id,
            issue_desc="客户反馈无法使用",
            status=status,
            created_at=created_at,
            attachments=[],
        )
        db.add(ticket)
        await db.flush()
        return ticket

    async def test_aftersales_followup_reminder_created_for_overdue_pending_ticket(self):
        now = datetime(2026, 7, 9, 12, 0, 0)
        async with self.Session() as db:
            ticket = await self._create_ticket(
                db,
                status="pending",
                created_at=now - timedelta(hours=25),
            )

            original_now = notification_service.now_utc
            notification_service.now_utc = lambda: now
            try:
                created = await notification_service.check_aftersales_followup_reminders(db)
            finally:
                notification_service.now_utc = original_now

            records = list(
                (await db.execute(select(NotificationRecord))).scalars().all()
            )

        self.assertEqual(len(created), 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].type, "aftersales_pending")
        self.assertEqual(records[0].ref_id, ticket.id)
        self.assertIn("超过 24 小时", records[0].content)

    async def test_aftersales_followup_reminder_deduplicates_same_ticket_same_day(self):
        now = datetime(2026, 7, 9, 12, 0, 0)
        async with self.Session() as db:
            ticket = await self._create_ticket(
                db,
                status="processing",
                created_at=now - timedelta(hours=50),
            )
            db.add(
                NotificationRecord(
                    type="aftersales_pending",
                    ref_id=ticket.id,
                    title="售后跟进提醒",
                    content="已有提醒",
                    status="unread",
                    scheduled_at=now,
                    sent_at=now,
                    created_at=now,
                )
            )
            await db.flush()

            original_now = notification_service.now_utc
            notification_service.now_utc = lambda: now
            try:
                created = await notification_service.check_aftersales_followup_reminders(db)
            finally:
                notification_service.now_utc = original_now

            records = list(
                (await db.execute(select(NotificationRecord))).scalars().all()
            )

        self.assertEqual(created, [])
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
