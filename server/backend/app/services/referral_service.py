"""推荐关系 + 返利生成服务 - 复刻前端 referralService.ts。

create_referral_and_rebate：建立推荐关系并生成返利（交易创建时调用）
含：自引用检测 / 循环引用检测 / 层级计算 / 返利金额计算
"""
from sqlalchemy import select, func
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

    优化：用 BFS 预先加载所有需要的 customers / customer_links / transactions，
    避免递归内 N+1 查询。SQL 次数从 O(N) 降为 3 次（固定）。
    """
    from ..models import Customer, Transaction

    # 1. BFS 遍历：从 root 出发，找出所有可达的 customer_id
    visited: set[int] = set()
    queue: list[int] = [root_customer_id]
    all_links_by_referrer: dict[int, list[CustomerLink]] = {}
    while queue:
        next_queue: list[int] = []
        for cid in queue:
            if cid in visited:
                continue
            visited.add(cid)
        # 批量加载这一层所有 referrer 的 CustomerLink
        if queue:
            rows = (await db.execute(
                select(CustomerLink).where(CustomerLink.referrer_id.in_(queue))
            )).scalars().all()
            for l in rows:
                all_links_by_referrer.setdefault(l.referrer_id, []).append(l)
                if l.buyer_id not in visited:
                    next_queue.append(l.buyer_id)
        queue = next_queue

    # 2. 批量加载所有相关 customers
    customer_rows = (await db.execute(
        select(Customer).where(Customer.id.in_(visited))
    )).scalars().all() if visited else []
    customer_by_id: dict[int, Customer] = {c.id: c for c in customer_rows if c.id is not None}

    # 3. 批量加载所有相关 transactions，按 customer_id 聚合 revenue
    revenue_by_customer: dict[int, float] = {}
    if visited:
        tx_rows = (await db.execute(
            select(Transaction.customer_id, func.coalesce(func.sum(Transaction.sale_price), 0.0))
            .where(
                Transaction.customer_id.in_(visited),
                Transaction.deleted_at.is_(None),
            )
            .group_by(Transaction.customer_id)
        )).all()
        revenue_by_customer = {cid: round2(float(total or 0.0)) for cid, total in tx_rows}

    # 4. 在内存中递归构建树
    def _build(cid: int, level: int, tree_visited: set[int]) -> dict:
        c = customer_by_id.get(cid)
        name = c.xianyu_nickname if c and not c.deleted_at else f"客户{cid}"
        if cid in tree_visited:
            return {"id": cid, "name": name, "level": level, "totalRevenue": 0.0, "children": []}
        tree_visited.add(cid)
        links = all_links_by_referrer.get(cid, [])
        children = [_build(l.buyer_id, level + 1, tree_visited) for l in links]
        return {
            "id": cid, "name": name, "level": level,
            "totalRevenue": revenue_by_customer.get(cid, 0.0), "children": children,
        }

    return _build(root_customer_id, 0, set())


async def get_referrer_rankings(db: AsyncSession) -> list[dict]:
    """介绍人排行。改用 SQL GROUP BY 替代全表加载内存聚合。

    语义保持与原实现一致：
    - introducedCount：每个 referrer 的不同 buyer 数量
    - broughtRevenue：所有 buyer 的累计成交额（status != 'closed'，未软删）
    - paidRebate / pendingRebate：referrer 名下 paid/pending 状态的返利总额
    排序：broughtRevenue 倒序。
    """
    from ..models import Customer, Transaction

    # 1. 每个推荐人的不同 buyer 数量
    intro_rows = (
        await db.execute(
            select(
                CustomerLink.referrer_id,
                func.count(func.distinct(CustomerLink.buyer_id)).label("cnt"),
            ).group_by(CustomerLink.referrer_id)
        )
    ).all()
    introduced_count: dict[int, int] = {
        rid: int(cnt) for rid, cnt in intro_rows if rid is not None
    }
    # 同时收集所有 referrer_id 用于后续查询 customers
    referrer_ids = list(introduced_count.keys())

    # 2. 每个 buyer 的累计成交额（status != 'closed'，未软删）
    # 然后 sum 到对应的 referrer（即：referrer_id → sum(buyer_revenue)）
    revenue_rows = (
        await db.execute(
            select(
                CustomerLink.referrer_id,
                func.coalesce(func.sum(Transaction.sale_price), 0.0),
            )
            .join(Transaction, Transaction.customer_id == CustomerLink.buyer_id)
            .where(
                Transaction.deleted_at.is_(None),
                Transaction.status != "closed",
            )
            .group_by(CustomerLink.referrer_id)
        )
    ).all()
    revenue_by_referrer: dict[int, float] = {
        rid: round2(float(total or 0.0)) for rid, total in revenue_rows if rid is not None
    }

    # 3. 每个 referrer 的 paid / pending 返利汇总
    rebate_rows = (
        await db.execute(
            select(
                RebateRecord.referrer_id,
                RebateRecord.status,
                func.coalesce(func.sum(RebateRecord.amount), 0.0),
            )
            .where(RebateRecord.status.in_(("paid", "pending")))
            .group_by(RebateRecord.referrer_id, RebateRecord.status)
        )
    ).all()
    paid_by_referrer: dict[int, float] = {}
    pending_by_referrer: dict[int, float] = {}
    for rid, status, amount in rebate_rows:
        if rid is None:
            continue
        if status == "paid":
            paid_by_referrer[rid] = round2(float(amount or 0.0))
        elif status == "pending":
            pending_by_referrer[rid] = round2(float(amount or 0.0))

    # 4. 批量加载推荐人客户信息（用于显示昵称）
    customer_by_id: dict[int, Customer] = {}
    if referrer_ids:
        rows = (await db.execute(
            select(Customer).where(Customer.id.in_(referrer_ids))
        )).scalars().all()
        customer_by_id = {c.id: c for c in rows if c.id is not None}

    # 5. 在内存中合并各维度并排序
    all_referrer_ids = set(introduced_count) | set(revenue_by_referrer) | set(paid_by_referrer) | set(pending_by_referrer)
    result = []
    for rid in all_referrer_ids:
        c = customer_by_id.get(rid)
        nickname = c.xianyu_nickname if c and not c.deleted_at else f"客户{rid}"
        result.append({
            "referrerId": rid,
            "nickname": nickname,
            "introducedCount": introduced_count.get(rid, 0),
            "broughtRevenue": revenue_by_referrer.get(rid, 0.0),
            "paidRebate": paid_by_referrer.get(rid, 0.0),
            "pendingRebate": pending_by_referrer.get(rid, 0.0),
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
