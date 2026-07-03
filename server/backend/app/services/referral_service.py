"""推荐关系 + 返利生成服务 - 复刻前端 referralService.ts。

create_referral_and_rebate：建立推荐关系并生成返利（交易创建时调用）
含：自引用检测 / 循环引用检测 / 层级计算 / 返利金额计算
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CustomerLink, RebateRecord
from ..utils.helpers import round2
from .settings_service import get_settings


class ReferralError(ValueError):
    pass


async def _would_create_cycle(db: AsyncSession, referrer_id: int, buyer_id: int) -> bool:
    """检测循环：buyer_id 是否是 referrer_id 的祖先（若是则建 referrer→buyer 会成环）。"""
    current = referrer_id
    visited: set[int] = set()
    while current is not None and current not in visited:
        visited.add(current)
        if current == buyer_id:
            return True
        parent = (
            await db.execute(
                select(CustomerLink).where(CustomerLink.buyer_id == current).limit(1)
            )
        ).scalar_one_or_none()
        current = parent.referrer_id if parent else None
    return False


async def _calc_referral_level(db: AsyncSession, buyer_id: int) -> int:
    """计算推荐层级：递归向上查找父链深度。"""
    visited: set[int] = set()
    current = buyer_id
    level = 0
    while current is not None and current not in visited:
        visited.add(current)
        parent = (
            await db.execute(
                select(CustomerLink).where(CustomerLink.buyer_id == current).limit(1)
            )
        ).scalar_one_or_none()
        if parent is None:
            break
        current = parent.referrer_id
        level += 1
    return level


async def create_referral_and_rebate(
    db: AsyncSession,
    *,
    referrer_id: int,
    buyer_id: int,
    transaction_id: int,
    profit: float,
    sale_price: float,
) -> None:
    """建立推荐关系（若不存在）并生成返利记录。复刻 createReferralAndRebate。"""
    if referrer_id == buyer_id:
        raise ReferralError("介绍人不能是买家本人")
    if await _would_create_cycle(db, referrer_id, buyer_id):
        raise ReferralError("检测到推荐链循环引用，无法建立该推荐关系")

    existing = (
        await db.execute(
            select(CustomerLink).where(
                CustomerLink.referrer_id == referrer_id,
                CustomerLink.buyer_id == buyer_id,
            ).limit(1)
        )
    ).scalar_one_or_none()

    level = await _calc_referral_level(db, referrer_id) + 1

    if existing is None:
        db.add(
            CustomerLink(
                referrer_id=referrer_id,
                buyer_id=buyer_id,
                transaction_id=transaction_id,
                level=level,
            )
        )
        await db.flush()

    s = await get_settings(db)
    base = sale_price if s.rebate_base == "sale" else profit
    amount = round2(base * s.rebate_rate)

    db.add(
        RebateRecord(
            referrer_id=referrer_id,
            buyer_id=buyer_id,
            transaction_id=transaction_id,
            amount=amount,
            rate=s.rebate_rate,
            status="pending",
        )
    )
    await db.flush()


# ==================== 查询聚合（复刻前端 referralService）====================

async def get_referral_tree(db: AsyncSession, root_customer_id: int) -> dict:
    """以某客户为根的推荐树。复刻 getReferralTree。

    返回嵌套结构 {id, name, level, totalRevenue, children: [...]}
    """
    from ..models import Customer, Transaction

    async def _revenue(customer_id: int, memo: dict[int, float]) -> float:
        if customer_id in memo:
            return memo[customer_id]
        stmt = select(Transaction).where(
            Transaction.customer_id == customer_id, Transaction.deleted_at.is_(None)
        )
        trades = list((await db.execute(stmt)).scalars().all())
        rev = round2(sum(t.sale_price for t in trades))
        memo[customer_id] = rev
        return rev

    async def _build(cid: int, level: int, visited: set[int], memo: dict[int, float]) -> dict:
        customer = await db.get(Customer, cid)
        name = customer.xianyu_nickname if customer and not customer.deleted_at else f"客户{cid}"
        if cid in visited:
            return {"id": cid, "name": name, "level": level, "totalRevenue": 0.0, "children": []}
        visited.add(cid)
        links = list((await db.execute(
            select(CustomerLink).where(CustomerLink.referrer_id == cid)
        )).scalars().all())
        children = [await _build(l.buyer_id, level + 1, visited, memo) for l in links]
        return {
            "id": cid, "name": name, "level": level,
            "totalRevenue": await _revenue(cid, memo), "children": children,
        }

    return await _build(root_customer_id, 0, set(), {})


async def get_referrer_rankings(db: AsyncSession) -> list[dict]:
    """介绍人排行。复刻 getReferrerRankings（4表join + 聚合 + 排序）。"""
    from ..models import Customer, Transaction
    # 一次性加载所需数据，内存聚合（与前端一致）
    links = list((await db.execute(select(CustomerLink))).scalars().all())
    rebates = list((await db.execute(select(RebateRecord))).scalars().all())
    all_trades = list((await db.execute(
        select(Transaction).where(Transaction.deleted_at.is_(None))
    )).scalars().all())
    revenue_by_customer: dict[int, float] = {}
    for t in all_trades:
        revenue_by_customer[t.customer_id] = revenue_by_customer.get(t.customer_id, 0.0) + t.sale_price

    customers = list((await db.execute(select(Customer))).scalars().all())
    customer_by_id = {c.id: c for c in customers if c.id is not None}

    agg: dict[int, dict] = {}
    for l in links:
        d = agg.setdefault(l.referrer_id, {"introduced": set(), "revenue": 0.0, "paid": 0.0, "pending": 0.0})
        d["introduced"].add(l.buyer_id)
        d["revenue"] += revenue_by_customer.get(l.buyer_id, 0.0)
    for r in rebates:
        d = agg.get(r.referrer_id)
        if not d:
            continue
        if r.status == "paid":
            d["paid"] += r.amount
        elif r.status == "pending":
            d["pending"] += r.amount

    result = []
    for rid, d in agg.items():
        c = customer_by_id.get(rid)
        result.append({
            "referrerId": rid,
            "nickname": c.xianyu_nickname if c and not c.deleted_at else f"客户{rid}",
            "introducedCount": len(d["introduced"]),
            "broughtRevenue": round2(d["revenue"]),
            "paidRebate": round2(d["paid"]),
            "pendingRebate": round2(d["pending"]),
        })
    result.sort(key=lambda x: x["broughtRevenue"], reverse=True)
    return result


async def get_introduced_by(db: AsyncSession, referrer_id: int) -> list[int]:
    """获取某介绍人的所有被介绍人 ID。"""
    links = list((await db.execute(
        select(CustomerLink).where(CustomerLink.referrer_id == referrer_id)
    )).scalars().all())
    return [l.buyer_id for l in links]


async def would_create_cycle_api(db: AsyncSession, referrer_id: int, buyer_id: int) -> dict:
    """供前端预检：建立 referrer→buyer 推荐关系是否会成环。"""
    return {"wouldCreateCycle": await _would_create_cycle(db, referrer_id, buyer_id)}


async def calc_referral_level_api(db: AsyncSession, buyer_id: int) -> dict:
    """供前端预检：某客户的推荐层级。"""
    return {"level": await _calc_referral_level(db, buyer_id)}
