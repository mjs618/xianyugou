"""交易服务 - 复刻前端 transactionService.ts 的完整级联逻辑。

create_transaction 在单个会话事务中：
1. 写交易
2. 重算客户累计（recalcCustomerStats）
3. 若为介绍来源，建立推荐关系 + 返利（createReferralAndRebate）

这是订单同步进账时复用的核心入口。
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction
from ..utils.helpers import calc_profit, calc_warranty_end, now_utc
from .audit_service import log_operation
from .customer_service import recalc_customer_stats
from .referral_service import create_referral_and_rebate
from .settings_service import get_settings


class TransactionError(ValueError):
    pass


def _validate_prices(sale_price: float, cost_price: float, warranty_days: Optional[int]) -> None:
    if sale_price < 0:
        raise TransactionError("售价不能为负数")
    if cost_price < 0:
        raise TransactionError("成本不能为负数")
    if warranty_days is not None and warranty_days < 0:
        raise TransactionError("质保天数不能为负数")


async def create_transaction(
    db: AsyncSession,
    *,
    customer_id: int,
    product_name: str,
    sale_price: float,
    cost_price: float,
    trade_at: datetime,
    shipped_at: Optional[datetime] = None,
    status: str = "pending",
    warranty_days: Optional[int] = None,
    source_type: str = "direct",
    xianyu_order_no: Optional[str] = None,
    product_template_id: Optional[int] = None,
    source_customer_id: Optional[int] = None,
    notes: Optional[str] = None,
    attachments: Optional[list[str]] = None,
    log: bool = True,
) -> Transaction:
    """创建交易（含级联）。复刻 createTransaction。"""
    _validate_prices(sale_price, cost_price, warranty_days)

    s = await get_settings(db)
    profit = calc_profit(sale_price, cost_price)
    wdays = warranty_days if warranty_days is not None else s.warranty_days
    warranty_start = shipped_at or trade_at
    warranty_end = calc_warranty_end(warranty_start, wdays) if status == "completed" and wdays > 0 else None

    now = now_utc()
    tx = Transaction(
        customer_id=customer_id,
        xianyu_order_no=xianyu_order_no,
        product_name=product_name,
        product_template_id=product_template_id,
        sale_price=sale_price,
        cost_price=cost_price,
        profit=profit,
        trade_at=trade_at,
        shipped_at=shipped_at if status == "completed" else None,
        status=status,
        warranty_end=warranty_end,
        warranty_days=wdays,
        source_type=source_type,
        source_customer_id=source_customer_id,
        notes=notes,
        attachments=attachments or [],
        version=0,
        created_at=now,
        updated_at=now,
    )
    db.add(tx)
    await db.flush()  # 拿到 tx.id

    # 级联：重算客户累计
    await recalc_customer_stats(db, customer_id)

    # 级联：介绍来源 → 推荐关系 + 返利
    if source_type == "introduced" and source_customer_id:
        await create_referral_and_rebate(
            db,
            referrer_id=source_customer_id,
            buyer_id=customer_id,
            transaction_id=tx.id,
            profit=profit,
            sale_price=sale_price,
        )

    if log:
        await log_operation(
            db, "transaction", "create", target_id=tx.id, target_name=product_name,
            detail=f"客户ID:{customer_id} 售价:{sale_price} 状态:{status}",
        )
    return tx


async def get_transaction(db: AsyncSession, tx_id: int) -> Optional[Transaction]:
    t = await db.get(Transaction, tx_id)
    if t is None or t.deleted_at is not None:
        return None
    return t


async def list_transactions(
    db: AsyncSession,
    *,
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    with_customer_name: bool = False,
) -> list:
    """交易列表，支持按客户/状态/日期范围过滤。

    with_customer_name=True 时返回 (Transaction, customer_name) 元组列表（dict 形式），
    供前端列表页直接展示客户名，避免 N+1 调用。
    """
    stmt = select(Transaction).where(Transaction.deleted_at.is_(None))
    if customer_id is not None:
        stmt = stmt.where(Transaction.customer_id == customer_id)
    if status:
        stmt = stmt.where(Transaction.status == status)
    if start is not None:
        stmt = stmt.where(Transaction.trade_at >= start)
    if end is not None:
        stmt = stmt.where(Transaction.trade_at <= end)
    stmt = stmt.order_by(Transaction.trade_at.desc())
    txs = list((await db.execute(stmt)).scalars().all())
    if not with_customer_name:
        return txs
    # 内联客户名
    from ..models import Customer
    customer_ids = {t.customer_id for t in txs}
    name_map: dict[int, str] = {}
    if customer_ids:
        customers = list(
            (await db.execute(select(Customer).where(Customer.id.in_(customer_ids)))).scalars().all()
        )
        name_map = {c.id: c.xianyu_nickname for c in customers if c.id is not None}
    result = []
    for t in txs:
        d = {c.name: getattr(t, c.name) for c in t.__table__.columns}
        d["customer_name"] = name_map.get(t.customer_id, "")
        result.append(d)
    return result


async def list_transactions_by_customer(db: AsyncSession, customer_id: int) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.customer_id == customer_id, Transaction.deleted_at.is_(None))
        .order_by(Transaction.trade_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_transactions_by_status(db: AsyncSession, status: str) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.status == status, Transaction.deleted_at.is_(None))
    )
    return list((await db.execute(stmt)).scalars().all())


async def change_status(db: AsyncSession, tx_id: int, status: str, expected_version: Optional[int] = None) -> Transaction:
    """修改交易状态。completed 时补质保到期；回退 pending 时清质保。"""
    t = await get_transaction(db, tx_id)
    if t is None:
        raise TransactionError("交易不存在")
    from ..utils.helpers import ConcurrencyError
    if expected_version is not None and expected_version != t.version:
        raise ConcurrencyError("交易已被其他操作修改，请刷新后重试")
    old_status = t.status

    t.status = status
    t.version += 1
    t.updated_at = now_utc()
    if status == "completed":
        if not t.shipped_at:
            t.shipped_at = now_utc()
        if t.warranty_days > 0 and not t.warranty_end:
            t.warranty_end = calc_warranty_end(t.shipped_at, t.warranty_days)
    if status == "pending":
        t.warranty_end = None
        t.shipped_at = None
    await db.flush()

    await log_operation(
        db, "transaction", "status_change", target_id=tx_id, target_name=t.product_name,
        detail=f"{old_status} → {status}",
    )
    return t


async def update_transaction(db: AsyncSession, tx_id: int, patch: dict, expected_version: Optional[int] = None) -> Transaction:
    """更新交易。复刻 updateTransaction 的级联（客户累计、返利联动）。"""
    t = await get_transaction(db, tx_id)
    if t is None:
        raise TransactionError("交易不存在")
    from ..utils.helpers import ConcurrencyError
    if expected_version is not None and expected_version != t.version:
        raise ConcurrencyError("交易已被其他操作修改，请刷新后重试")

    if "sale_price" in patch and patch["sale_price"] is not None and patch["sale_price"] < 0:
        raise TransactionError("售价不能为负数")
    if "cost_price" in patch and patch["cost_price"] is not None and patch["cost_price"] < 0:
        raise TransactionError("成本不能为负数")

    price_changed = "sale_price" in patch or "cost_price" in patch
    if price_changed:
        sale = patch.get("sale_price", t.sale_price)
        cost = patch.get("cost_price", t.cost_price)
        t.profit = calc_profit(sale, cost)

    if "warranty_days" in patch and patch["warranty_days"] is not None:
        if patch["warranty_days"] < 0:
            raise TransactionError("质保天数不能为负数")
        t.warranty_days = patch["warranty_days"]

    if "trade_at" in patch and patch["trade_at"]:
        t.trade_at = patch["trade_at"]
    if "shipped_at" in patch:
        t.shipped_at = patch["shipped_at"]

    # 其余字段
    for k in ("xianyu_order_no", "product_name", "product_template_id", "sale_price",
              "cost_price", "status", "source_type", "source_customer_id", "notes", "attachments"):
        if k in patch:
            setattr(t, k, patch[k])

    if t.status == "completed":
        warranty_start = t.shipped_at or t.trade_at
        t.warranty_end = calc_warranty_end(warranty_start, t.warranty_days) if t.warranty_days > 0 else None
    elif t.status == "pending":
        t.warranty_end = None
        t.shipped_at = None

    t.version += 1
    t.updated_at = now_utc()
    await db.flush()

    # 级联：客户累计
    await recalc_customer_stats(db, t.customer_id)
    if patch.get("customer_id") and patch["customer_id"] != t.customer_id:
        await recalc_customer_stats(db, patch["customer_id"])

    await log_operation(
        db, "transaction", "update", target_id=tx_id, target_name=t.product_name,
        detail=f"修改字段: {', '.join(patch.keys())}",
    )
    return t


async def soft_delete_transaction(db: AsyncSession, tx_id: int) -> None:
    """软删除交易 + 级联清理（软删售后工单、取消返利）。"""
    from ..models import AfterSales, RebateRecord
    t = await db.get(Transaction, tx_id)
    if t is None or t.deleted_at is not None:
        return
    now = now_utc()
    t.deleted_at = now
    t.updated_at = now

    # 软删除关联售后工单
    tickets = list(
        (await db.execute(select(AfterSales).where(AfterSales.transaction_id == tx_id))).scalars().all()
    )
    for a in tickets:
        if a.deleted_at is None:
            a.deleted_at = now

    # 取消关联返利（pending→cancelled）
    rebates = list(
        (await db.execute(select(RebateRecord).where(RebateRecord.transaction_id == tx_id))).scalars().all()
    )
    for r in rebates:
        if r.status == "pending":
            r.status = "cancelled"
            r.notes = "交易已删除，自动取消返利"

    await db.flush()
    # 级联：重算客户累计
    await recalc_customer_stats(db, t.customer_id)

    await log_operation(db, "transaction", "delete", target_id=tx_id, target_name=t.product_name)
