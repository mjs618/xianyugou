"""客户服务 - 复刻前端 customerService.ts 的核心逻辑。

关键函数：
- createCustomer：创建客户（昵称唯一性校验）
- recalcCustomerStats：重算客户累计消费/笔数/等级（交易级联时调用）
- updateCustomer / softDeleteCustomer：乐观锁 + 级联校验
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Customer, Transaction
from ..utils.helpers import evaluate_level, now_utc
from .audit_service import log_operation
from .settings_service import get_settings


class CustomerError(ValueError):
    pass


async def find_by_nickname(db: AsyncSession, nickname: str) -> Optional[Customer]:
    """按昵称查找（不区分大小写，排除已软删除）"""
    stmt = select(Customer).where(
        Customer.deleted_at.is_(None),
        func.lower(Customer.xianyu_nickname) == nickname.strip().lower(),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_customer(
    db: AsyncSession,
    *,
    xianyu_nickname: str,
    contact_info: Optional[str] = None,
    notes: Optional[str] = None,
    is_blacklist: bool = False,
    log: bool = True,
) -> Customer:
    """创建客户。昵称唯一性校验。"""
    nickname = (xianyu_nickname or "").strip()
    if not nickname:
        raise CustomerError("客户昵称不能为空")
    existing = await find_by_nickname(db, nickname)
    if existing:
        raise CustomerError(f'客户昵称"{nickname}"已存在（不区分大小写）')

    now = now_utc()
    c = Customer(
        xianyu_nickname=nickname,
        contact_info=contact_info,
        total_spent=0.0,
        trade_count=0,
        level="normal",
        tags=[],
        is_blacklist=is_blacklist,
        notes=notes,
        version=0,
        created_at=now,
        updated_at=now,
    )
    db.add(c)
    await db.flush()
    if log:
        await log_operation(db, "customer", "create", target_id=c.id, target_name=nickname)
    return c


async def get_customer(db: AsyncSession, customer_id: int) -> Optional[Customer]:
    c = await db.get(Customer, customer_id)
    if c is None or c.deleted_at is not None:
        return None
    return c


async def list_customers(db: AsyncSession) -> list[Customer]:
    stmt = select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def search_customers(db: AsyncSession, keyword: str) -> list[Customer]:
    kw = keyword.strip().lower()
    stmt = select(Customer).where(
        Customer.deleted_at.is_(None),
        or_(
            func.lower(Customer.xianyu_nickname).contains(kw),
            func.lower(func.coalesce(Customer.contact_info, "")).contains(kw),
        ),
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_customer(db: AsyncSession, customer_id: int, patch: dict, expected_version: Optional[int] = None) -> Customer:
    """更新客户。乐观锁 + 昵称唯一性校验。"""
    c = await get_customer(db, customer_id)
    if c is None:
        raise CustomerError("客户不存在")

    # 乐观锁：传入 expected_version 时校验一致性
    from ..utils.helpers import ConcurrencyError
    if expected_version is not None and expected_version != c.version:
        raise ConcurrencyError("客户已被其他操作修改，请刷新后重试")

    expected_ver = c.version
    if "xianyu_nickname" in patch:
        new_nick = (patch["xianyu_nickname"] or "").strip()
        if not new_nick:
            raise CustomerError("客户昵称不能为空")
        if new_nick.lower() != c.xianyu_nickname.lower():
            existing = await find_by_nickname(db, new_nick)
            if existing and existing.id != customer_id:
                raise CustomerError(f'客户昵称"{new_nick}"已存在（不区分大小写）')
        patch["xianyu_nickname"] = new_nick

    changed_keys = list(patch.keys())
    for k, v in patch.items():
        if hasattr(c, k):
            setattr(c, k, v)
    c.version = expected_ver + 1
    c.updated_at = now_utc()
    await db.flush()

    await log_operation(
        db, "customer", "update", target_id=customer_id,
        target_name=patch.get("xianyu_nickname", c.xianyu_nickname),
        detail=f"修改字段: {', '.join(changed_keys)}",
    )
    return c


async def soft_delete_customer(db: AsyncSession, customer_id: int) -> None:
    c = await get_customer(db, customer_id)
    if c is None:
        raise CustomerError("客户不存在")

    # 校验无关联未删除交易
    cnt_stmt = select(func.count(Transaction.id)).where(
        Transaction.customer_id == customer_id, Transaction.deleted_at.is_(None)
    )
    active = (await db.execute(cnt_stmt)).scalar_one()
    if active > 0:
        raise CustomerError(f"该客户有 {active} 笔未删除交易，请先删除交易后再删除客户")

    c.deleted_at = now_utc()
    await db.flush()
    await log_operation(db, "customer", "delete", target_id=customer_id, target_name=c.xianyu_nickname)


async def recalc_customer_stats(db: AsyncSession, customer_id: int) -> None:
    """重算客户累计消费/笔数/首单时间/等级（交易级联核心）。

    复刻 customerService.recalcCustomerStats。
    """
    c = await db.get(Customer, customer_id)
    if c is None or c.deleted_at is not None:
        return
    stmt = select(Transaction).where(
        Transaction.customer_id == customer_id, Transaction.deleted_at.is_(None)
    )
    trades = list((await db.execute(stmt)).scalars().all())
    total_spent = round(sum(t.sale_price for t in trades) + 1e-9, 2)
    trade_count = len(trades)
    # 统一转 naive UTC 再比较，避免 aware/naive datetime 混合导致 TypeError
    def _naive(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    first_trade_at = min((_naive(t.trade_at) for t in trades if t.trade_at), default=None)

    s = await get_settings(db)
    level = evaluate_level(total_spent, trade_count, s)

    c.total_spent = total_spent
    c.trade_count = trade_count
    c.first_trade_at = first_trade_at
    c.level = level
    c.updated_at = now_utc()
    c.version += 1
    await db.flush()


async def recalc_all_customers_stats(db: AsyncSession) -> int:
    """批量重算所有未删除客户（等级阈值变更后调用）。"""
    all_customers = await list_customers(db)
    for c in all_customers:
        await recalc_customer_stats(db, c.id)
    return len(all_customers)


async def toggle_blacklist(db: AsyncSession, customer_id: int) -> Customer:
    c = await get_customer(db, customer_id)
    if c is None:
        raise CustomerError("客户不存在")
    c.is_blacklist = not c.is_blacklist
    c.updated_at = now_utc()
    await db.flush()
    await log_operation(
        db, "customer", "update", target_id=customer_id, target_name=c.xianyu_nickname,
        detail=f"黑名单: {'取消' if not c.is_blacklist else '加入'}",
    )
    return c
