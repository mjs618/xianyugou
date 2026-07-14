"""F3-a 测试补充：rebate_service 单元测试。

覆盖点：
1. _validate_transition: 合法流转 / 非法流转 / frm==to 快捷通过
2. list_rebates: 按 created_at desc 排序返回
3. get_rebate: 存在 / 不存在
4. get_rebate_by_transaction: 返回关联 / 无关联 None
5. list_by_referrer: 按 referrer_id 过滤
6. get_pending_count / get_pending_total / get_total_paid: 聚合查询
7. mark_paid: 成功 + 设置 paid_at / 不存在抛错 / 非法状态流转抛错 / 更新 notes
8. cancel_rebate: 成功 / 不存在抛错 / 非法状态流转抛错
9. batch_pay: 批量正常 / 跳过非法状态 / 跳过不存在的 id / 去重保序
10. recalc_pending_rebates: sale base / profit base / rate+amount 不变跳过 / 不存在的 transaction 跳过
"""
import unittest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Customer, RebateRecord, Settings, Transaction
from app.services.rebate_service import (
    RebateError,
    VALID_TRANSITIONS,
    _validate_transition,
    batch_pay,
    cancel_rebate,
    get_pending_count,
    get_pending_total,
    get_rebate,
    get_rebate_by_transaction,
    get_total_paid,
    list_by_referrer,
    list_rebates,
    mark_paid,
    recalc_pending_rebates,
)
from app.utils.helpers import now_utc


def _make_rebate(
    *,
    id: int,
    referrer_id: int = 10,
    buyer_id: int = 20,
    transaction_id: int = 1,
    amount: float = 10.0,
    rate: float = 0.1,
    status: str = "pending",
    notes: str | None = None,
    created_at: datetime | None = None,
) -> RebateRecord:
    return RebateRecord(
        id=id,
        referrer_id=referrer_id,
        buyer_id=buyer_id,
        transaction_id=transaction_id,
        amount=amount,
        rate=rate,
        status=status,
        notes=notes,
        created_at=created_at or now_utc(),
    )


def _make_transaction(*, id: int, sale_price: float = 100.0, profit: float = 30.0) -> Transaction:
    return Transaction(
        id=id,
        customer_id=20,
        product_name="测试商品",
        sale_price=sale_price,
        cost_price=sale_price - profit,
        profit=profit,
        trade_at=datetime(2026, 7, 1, 10, 0, 0),
        status="completed",
        warranty_days=30,
        channel="xianyu",
    )


def _make_customer(*, id: int, nickname: str = "客户A") -> Customer:
    return Customer(id=id, xianyu_nickname=nickname)


class ValidateTransitionTests(unittest.TestCase):
    """_validate_transition 状态机校验。"""

    def test_same_status_no_op(self):
        """frm == to 时直接返回（无操作）。"""
        _validate_transition("pending", "pending")
        _validate_transition("paid", "paid")
        _validate_transition("cancelled", "cancelled")

    def test_legal_transitions(self):
        """合法流转不抛错。"""
        for frm, allowed_list in VALID_TRANSITIONS.items():
            for to in allowed_list:
                _validate_transition(frm, to)

    def test_illegal_pending_to_paid_after_cancellation(self):
        """cancelled → paid 非法。"""
        with self.assertRaises(RebateError):
            _validate_transition("cancelled", "paid")

    def test_illegal_resurrect_cancelled(self):
        """cancelled → 任何状态都非法（cancelled 流转列表为空）。"""
        with self.assertRaises(RebateError):
            _validate_transition("cancelled", "pending")
        with self.assertRaises(RebateError):
            _validate_transition("cancelled", "paid")

    def test_illegal_paid_back_to_pending(self):
        """paid → pending 非法。"""
        with self.assertRaises(RebateError):
            _validate_transition("paid", "pending")

    def test_unknown_status_raises(self):
        """未知状态（不在 VALID_TRANSITIONS 中）抛错。"""
        with self.assertRaises(RebateError):
            _validate_transition("unknown", "paid")


class RebateServiceTests(unittest.IsolatedAsyncioTestCase):
    """rebate_service 数据库相关测试。"""

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

    async def _seed_settings(self, db, *, rebate_base: str = "sale", rebate_rate: float = 0.1):
        """注入 Settings 单例。"""
        s = Settings(
            id=1,
            rebate_base=rebate_base,
            rebate_rate=rebate_rate,
            warranty_days=30,
        )
        db.add(s)
        await db.flush()

    # ==================== list_rebates / get_rebate ====================

    async def test_list_rebates_returns_all_ordered_by_created_at_desc(self):
        async with self.Session() as db:
            now = now_utc()
            db.add(_make_rebate(id=1, created_at=now - timedelta(hours=2)))
            db.add(_make_rebate(id=2, created_at=now - timedelta(hours=1)))
            db.add(_make_rebate(id=3, created_at=now))
            await db.commit()
            result = await list_rebates(db)
            self.assertEqual([r.id for r in result], [3, 2, 1])

    async def test_get_rebate_found_and_not_found(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1))
            await db.commit()
            found = await get_rebate(db, 1)
            self.assertIsNotNone(found)
            self.assertEqual(found.id, 1)
            missing = await get_rebate(db, 999)
            self.assertIsNone(missing)

    async def test_get_rebate_by_transaction(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, transaction_id=42))
            await db.commit()
            r = await get_rebate_by_transaction(db, 42)
            self.assertIsNotNone(r)
            self.assertEqual(r.id, 1)
            none_r = await get_rebate_by_transaction(db, 999)
            self.assertIsNone(none_r)

    async def test_list_by_referrer(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, referrer_id=10))
            db.add(_make_rebate(id=2, referrer_id=20))
            db.add(_make_rebate(id=3, referrer_id=10))
            await db.commit()
            r10 = await list_by_referrer(db, 10)
            self.assertEqual({r.id for r in r10}, {1, 3})
            r20 = await list_by_referrer(db, 20)
            self.assertEqual({r.id for r in r20}, {2})
            r_none = await list_by_referrer(db, 999)
            self.assertEqual(r_none, [])

    # ==================== 聚合查询 ====================

    async def test_get_pending_count_total_paid(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, amount=10.0, status="pending"))
            db.add(_make_rebate(id=2, amount=20.0, status="pending"))
            db.add(_make_rebate(id=3, amount=50.0, status="paid"))
            db.add(_make_rebate(id=4, amount=5.0, status="cancelled"))
            await db.commit()
            self.assertEqual(await get_pending_count(db), 2)
            self.assertAlmostEqual(await get_pending_total(db), 30.0, places=2)
            self.assertAlmostEqual(await get_total_paid(db), 50.0, places=2)

    async def test_aggregates_return_zero_when_empty(self):
        async with self.Session() as db:
            self.assertEqual(await get_pending_count(db), 0)
            self.assertEqual(await get_pending_total(db), 0.0)
            self.assertEqual(await get_total_paid(db), 0.0)

    # ==================== mark_paid / cancel_rebate ====================

    async def test_mark_paid_success_sets_paid_at_and_notes(self):
        async with self.Session() as db:
            r = _make_rebate(id=1, status="pending", notes=None)
            db.add(r)
            await db.commit()
            updated = await mark_paid(db, 1, notes="线下现金")
            self.assertEqual(updated.status, "paid")
            self.assertIsNotNone(updated.paid_at)
            self.assertEqual(updated.notes, "线下现金")

    async def test_mark_paid_not_found_raises(self):
        async with self.Session() as db:
            with self.assertRaises(RebateError):
                await mark_paid(db, 999)

    async def test_mark_paid_illegal_transition_raises(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="cancelled"))
            await db.commit()
            with self.assertRaises(RebateError):
                await mark_paid(db, 1)

    async def test_cancel_rebate_success_from_paid(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="paid"))
            await db.commit()
            updated = await cancel_rebate(db, 1, notes="客户拒收")
            self.assertEqual(updated.status, "cancelled")
            self.assertEqual(updated.notes, "客户拒收")

    async def test_cancel_rebate_not_found_raises(self):
        async with self.Session() as db:
            with self.assertRaises(RebateError):
                await cancel_rebate(db, 999)

    async def test_cancel_rebate_from_cancelled_is_no_op(self):
        """已 cancelled → cancelled 是 idempotent no-op（不抛错，无状态变化）。

        _validate_transition 对同状态直接返回。
        """
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="cancelled"))
            await db.commit()
            # 同状态不抛错
            updated = await cancel_rebate(db, 1, notes="再次取消")
            self.assertEqual(updated.status, "cancelled")
            self.assertEqual(updated.notes, "再次取消")

    # ==================== batch_pay ====================

    async def test_batch_pay_normal(self):
        """2 pending + 1 paid：paid 被跳过（修复后只处理 pending 状态）。

        修复前 bug：_validate_transition 对 paid→paid 是 idempotent no-op，
        导致 paid 状态被误判为合法，纳入 valid 列表。
        修复后：显式只允许 pending 状态进入结算。
        """
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="pending"))
            db.add(_make_rebate(id=2, status="pending"))
            db.add(_make_rebate(id=3, status="paid"))  # 跳过
            await db.commit()
            result = await batch_pay(db, [1, 2, 3])
            self.assertEqual(result["updated"], 2)
            self.assertEqual(result["skipped"], 1)

    async def test_batch_pay_skips_non_pending_statuses(self):
        """paid 和 cancelled 都被跳过，只有 pending 进入结算。"""
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="pending"))
            db.add(_make_rebate(id=2, status="paid"))
            db.add(_make_rebate(id=3, status="cancelled"))
            await db.commit()
            result = await batch_pay(db, [1, 2, 3])
            self.assertEqual(result["updated"], 1)
            self.assertEqual(result["skipped"], 2)

    async def test_batch_pay_skips_unknown_ids(self):
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="pending"))
            await db.commit()
            result = await batch_pay(db, [1, 999, 1000])
            self.assertEqual(result["updated"], 1)
            self.assertEqual(result["skipped"], 2)

    async def test_batch_pay_deduplicates_ids(self):
        """去重保序：传入 [1, 1, 2] 应只处理 1 和 2 各一次。"""
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="pending"))
            db.add(_make_rebate(id=2, status="pending"))
            await db.commit()
            result = await batch_pay(db, [1, 1, 2, 2, 1])
            self.assertEqual(result["updated"], 2)
            self.assertEqual(result["skipped"], 0)

    async def test_batch_pay_all_non_pending(self):
        """所有 id 都非 pending（paid/cancelled）→ updated=0, skipped=N。"""
        async with self.Session() as db:
            db.add(_make_rebate(id=1, status="cancelled"))
            db.add(_make_rebate(id=2, status="paid"))
            await db.commit()
            result = await batch_pay(db, [1, 2])
            self.assertEqual(result["updated"], 0)
            self.assertEqual(result["skipped"], 2)

    async def test_batch_pay_empty_list(self):
        async with self.Session() as db:
            result = await batch_pay(db, [])
            self.assertEqual(result["updated"], 0)
            self.assertEqual(result["skipped"], 0)

    # ==================== recalc_pending_rebates ====================

    async def test_recalc_sale_base(self):
        """rebate_base=sale：amount = sale_price * rate。"""
        async with self.Session() as db:
            await self._seed_settings(db, rebate_base="sale", rebate_rate=0.1)
            db.add(_make_customer(id=20, nickname="买家"))
            db.add(_make_transaction(id=1, sale_price=100.0, profit=30.0))
            # 原 amount=5，新 amount 应=100*0.1=10 → 更新
            db.add(_make_rebate(id=1, transaction_id=1, amount=5.0, rate=0.05, status="pending"))
            await db.commit()
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 1)
            r = await get_rebate(db, 1)
            self.assertAlmostEqual(r.amount, 10.0, places=2)
            self.assertAlmostEqual(r.rate, 0.1, places=4)

    async def test_recalc_profit_base(self):
        """rebate_base=profit：amount = profit * rate。"""
        async with self.Session() as db:
            await self._seed_settings(db, rebate_base="profit", rebate_rate=0.2)
            db.add(_make_customer(id=20, nickname="买家"))
            db.add(_make_transaction(id=1, sale_price=100.0, profit=30.0))
            # 原 amount=10, rate=0.1 → 新 amount=30*0.2=6, rate=0.2 → 更新
            db.add(_make_rebate(id=1, transaction_id=1, amount=10.0, rate=0.1, status="pending"))
            await db.commit()
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 1)
            r = await get_rebate(db, 1)
            self.assertAlmostEqual(r.amount, 6.0, places=2)
            self.assertAlmostEqual(r.rate, 0.2, places=4)

    async def test_recalc_skips_when_amount_and_rate_unchanged(self):
        """amount + rate 均未变化时不计入 updated。"""
        async with self.Session() as db:
            await self._seed_settings(db, rebate_base="sale", rebate_rate=0.1)
            db.add(_make_customer(id=20, nickname="买家"))
            db.add(_make_transaction(id=1, sale_price=100.0, profit=30.0))
            db.add(_make_rebate(id=1, transaction_id=1, amount=10.0, rate=0.1, status="pending"))
            await db.commit()
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 0)

    async def test_recalc_skips_non_pending(self):
        """已支付/已取消的返利不参与重算（query 仅选 pending）。"""
        async with self.Session() as db:
            await self._seed_settings(db, rebate_base="sale", rebate_rate=0.1)
            db.add(_make_customer(id=20, nickname="买家"))
            db.add(_make_transaction(id=1, sale_price=100.0, profit=30.0))
            db.add(_make_rebate(id=1, transaction_id=1, amount=5.0, rate=0.05, status="paid"))
            await db.commit()
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 0)

    async def test_recalc_skips_when_transaction_missing(self):
        """pending 返利但关联交易不存在 → 跳过（不入 updated）。"""
        async with self.Session() as db:
            await self._seed_settings(db, rebate_base="sale", rebate_rate=0.1)
            # 故意不创建 transaction
            db.add(_make_rebate(id=1, transaction_id=999, amount=5.0, rate=0.05, status="pending"))
            await db.commit()
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 0)

    async def test_recalc_handles_no_pending(self):
        """无 pending 返利 → 0 更新。"""
        async with self.Session() as db:
            await self._seed_settings(db)
            updated = await recalc_pending_rebates(db)
            self.assertEqual(updated, 0)


if __name__ == "__main__":
    unittest.main()
