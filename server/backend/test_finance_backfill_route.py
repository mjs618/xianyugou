"""POST /api/finance/backfill-cost 路由测试。

验证：
1. 路由存在并返回正确的结构 {matched, backfilled, skipped_no_template, skipped_zero_cost_template}
2. 只回填 cost_price=0 的交易（不覆盖手动设置的成本）
3. 通过 XianyuOrder.raw_order.itemId 反查 product_templates.source_xianyu_item_id 匹配
4. 回填后重算受影响客户的累计消费/笔数/等级
5. 无 cost_price=0 交易时返回全 0 的空结果
"""
import unittest
from datetime import datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Customer, ProductTemplate, Transaction, XianyuOrder


def _make_raw_order(order_id: int, item_id: str) -> dict:
    """构造闲鱼原始订单（commonData.itemId 是真实位置）。"""
    return {
        "commonData": {
            "orderId": order_id,
            "orderStatus": "交易成功",
            "itemId": item_id,
        },
        "itemVO": {"title": "测试商品"},
        "priceVO": {"confirmFee": "100.00"},
    }


class BackfillCostRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

    async def asyncTearDown(self):
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def _seed_customer(self, db) -> Customer:
        c = Customer(
            xianyu_nickname="测试买家",
            total_spent=0.0,
            trade_count=0,
            level="normal",
            tags=[],
            is_blacklist=False,
            version=0,
            created_at=datetime(2026, 7, 1),
            updated_at=datetime(2026, 7, 1),
        )
        db.add(c)
        await db.flush()
        return c

    async def test_backfill_returns_empty_when_no_zero_cost_transactions(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/finance/backfill-cost")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body,
            {
                "matched": 0,
                "backfilled": 0,
                "skipped_no_template": 0,
                "skipped_zero_cost_template": 0,
            },
        )

    async def test_backfill_fills_zero_cost_transaction_from_matching_template(self):
        async with self.Session() as db:
            customer = await self._seed_customer(db)
            # 1 笔 cost_price=0 的交易（待回填）
            tx = Transaction(
                customer_id=customer.id,
                product_name="测试商品",
                sale_price=100.0,
                cost_price=0.0,
                profit=100.0,
                trade_at=datetime(2026, 7, 10),
                status="completed",
                warranty_days=30,
                source_type="direct",
                channel="xianyu",
                version=0,
            )
            db.add(tx)
            await db.flush()
            # 关联 XianyuOrder 镜像（projected_transaction_id 反查）
            db.add(XianyuOrder(
                account_id=1,
                order_no="ORD-1",
                sale_price=100.0,
                raw_order=_make_raw_order(1001, "ITEM-1001"),
                projected_transaction_id=tx.id,
            ))
            # 匹配的模板：source_xianyu_item_id 与 raw_order.itemId 一致
            db.add(ProductTemplate(
                name="测试商品模板",
                default_cost=30.0,
                default_sale_price=100.0,
                warranty_days=30,
                is_active=True,
                source_xianyu_item_id="ITEM-1001",
            ))
            await db.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/finance/backfill-cost")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["matched"], 1)
        self.assertEqual(body["backfilled"], 1)
        self.assertEqual(body["skipped_no_template"], 0)
        self.assertEqual(body["skipped_zero_cost_template"], 0)

        # 验证交易已被回填
        async with self.Session() as db:
            updated = await db.get(Transaction, tx.id)
            self.assertEqual(updated.cost_price, 30.0)
            self.assertEqual(updated.product_template_id, (await db.get(ProductTemplate, 1)).id)
            self.assertEqual(updated.profit, 70.0)
            # 客户累计消费应被重算（包含 sale_price=100）
            refreshed_customer = await db.get(Customer, customer.id)
            self.assertEqual(refreshed_customer.total_spent, 100.0)
            self.assertEqual(refreshed_customer.trade_count, 1)

    async def test_backfill_skips_non_zero_cost_transactions(self):
        """已手动设置成本（cost_price>0）的交易不应被覆盖。"""
        async with self.Session() as db:
            customer = await self._seed_customer(db)
            tx = Transaction(
                customer_id=customer.id,
                product_name="已设成本商品",
                sale_price=100.0,
                cost_price=25.0,  # 非 0：不应被回填
                profit=75.0,
                trade_at=datetime(2026, 7, 10),
                status="completed",
                warranty_days=30,
                source_type="direct",
                channel="xianyu",
                version=0,
            )
            db.add(tx)
            await db.flush()
            db.add(XianyuOrder(
                account_id=1,
                order_no="ORD-2",
                sale_price=100.0,
                raw_order=_make_raw_order(1002, "ITEM-1002"),
                projected_transaction_id=tx.id,
            ))
            db.add(ProductTemplate(
                name="模板2",
                default_cost=99.0,  # 即使模板成本更高，也不覆盖
                warranty_days=30,
                is_active=True,
                source_xianyu_item_id="ITEM-1002",
            ))
            await db.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/finance/backfill-cost")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        # 没有 cost_price=0 的交易，所以全部 0
        self.assertEqual(body["matched"], 0)
        self.assertEqual(body["backfilled"], 0)

        async with self.Session() as db:
            updated = await db.get(Transaction, tx.id)
            # 成本保持原值
            self.assertEqual(updated.cost_price, 25.0)
            self.assertIsNone(updated.product_template_id)

    async def test_backfill_counts_skipped_no_template_when_mirror_missing(self):
        """有 cost_price=0 交易但无镜像/无 itemId/无匹配模板时计入 skipped_no_template。"""
        async with self.Session() as db:
            customer = await self._seed_customer(db)
            tx = Transaction(
                customer_id=customer.id,
                product_name="无镜像商品",
                sale_price=50.0,
                cost_price=0.0,
                profit=50.0,
                trade_at=datetime(2026, 7, 10),
                status="completed",
                warranty_days=30,
                source_type="direct",
                channel="xianyu",
                version=0,
            )
            db.add(tx)
            await db.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/finance/backfill-cost")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["matched"], 0)
        self.assertEqual(body["backfilled"], 0)
        self.assertEqual(body["skipped_no_template"], 1)
        self.assertEqual(body["skipped_zero_cost_template"], 0)

    async def test_backfill_counts_skipped_zero_cost_template(self):
        """匹配到模板但模板 default_cost=0 时计入 skipped_zero_cost_template。"""
        async with self.Session() as db:
            customer = await self._seed_customer(db)
            tx = Transaction(
                customer_id=customer.id,
                product_name="零成本模板商品",
                sale_price=80.0,
                cost_price=0.0,
                profit=80.0,
                trade_at=datetime(2026, 7, 10),
                status="completed",
                warranty_days=30,
                source_type="direct",
                channel="xianyu",
                version=0,
            )
            db.add(tx)
            await db.flush()
            db.add(XianyuOrder(
                account_id=1,
                order_no="ORD-3",
                sale_price=80.0,
                raw_order=_make_raw_order(1003, "ITEM-1003"),
                projected_transaction_id=tx.id,
            ))
            db.add(ProductTemplate(
                name="零成本模板",
                default_cost=0.0,  # 模板成本仍为 0
                warranty_days=30,
                is_active=True,
                source_xianyu_item_id="ITEM-1003",
            ))
            await db.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/finance/backfill-cost")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["matched"], 1)
        self.assertEqual(body["backfilled"], 0)
        self.assertEqual(body["skipped_no_template"], 0)
        self.assertEqual(body["skipped_zero_cost_template"], 1)


if __name__ == "__main__":
    unittest.main()
