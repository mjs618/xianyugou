import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import XianyuAccount
from app.services.xianyu.order_service import SyncAlreadyRunningError, upsert_order_mirror


class XianyuOrderRouteTests(unittest.IsolatedAsyncioTestCase):
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

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def test_list_account_orders_returns_sanitized_mirror_rows(self):
        async with self.Session() as db:
            account = XianyuAccount(nickname="safe-account", cookies="encrypted-cookie")
            db.add(account)
            await db.flush()
            await upsert_order_mirror(
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
                    "sensitiveRawCookieLikeField": "COOKIE_SENTINEL",
                },
            )
            await db.commit()
            account_id = account.id

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/xianyu/accounts/{account_id}/orders")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["order_no"], "ORDER-1")
        self.assertEqual(row["order_status"], "TRADE_FINISHED")
        self.assertEqual(row["buyer_nick"], "buyer-a")
        self.assertEqual(row["product_name"], "product-a")
        self.assertEqual(row["sale_price"], 88.0)
        self.assertNotIn("raw_order", row)
        self.assertNotIn("COOKIE_SENTINEL", response.text)

    async def test_sync_orders_returns_conflict_when_account_sync_is_running(self):
        with patch(
            "app.routers.xianyu.sync_orders_for_account",
            side_effect=SyncAlreadyRunningError("running"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.post("/api/xianyu/accounts/1/sync-orders")

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
