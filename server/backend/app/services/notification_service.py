"""通知服务 - 复刻前端 notificationService.ts。

迁移分工：
- 通知 CRUD + pending-summary + 提醒生成：后端实现
- 浏览器通知权限/弹窗：留前端（new Notification 是浏览器能力）
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import NotificationRecord, Customer, Transaction
from ..utils.helpers import now_utc
from .settings_service import get_settings


def _same_day(a: datetime, b: datetime) -> bool:
    """判断两个 datetime 是否同一天（统一 naive 比较）"""
    def _naive(d):
        return d.replace(tzinfo=None) if d and d.tzinfo else d
    na, nb = _naive(a), _naive(b)
    return na.date() == nb.date() if na and nb else False


async def _find_today_notification(
    db: AsyncSession, ntype: str, ref_id: Optional[int], now: datetime
) -> Optional[NotificationRecord]:
    """防重：查找当天同类型同 ref 的通知。"""
    stmt = select(NotificationRecord).where(
        NotificationRecord.type == ntype,
        func.date(NotificationRecord.scheduled_at) == now.date(),
    )
    if ref_id is not None:
        stmt = stmt.where(NotificationRecord.ref_id == ref_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none()


async def get_unread_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(NotificationRecord.id)).where(NotificationRecord.status == "unread")
        )
    ).scalar_one()


async def list_notifications(db: AsyncSession, limit: int = 50) -> list[NotificationRecord]:
    stmt = (
        select(NotificationRecord)
        .order_by(NotificationRecord.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def mark_as_read(db: AsyncSession, nid: int) -> None:
    n = await db.get(NotificationRecord, nid)
    if n:
        n.status = "read"


async def mark_all_as_read(db: AsyncSession) -> None:
    await db.execute(
        update(NotificationRecord).where(NotificationRecord.status == "unread").values(status="read")
    )


async def dismiss(db: AsyncSession, nid: int) -> None:
    n = await db.get(NotificationRecord, nid)
    if n:
        n.status = "dismissed"


async def get_pending_summary(db: AsyncSession) -> dict:
    """待处理事项汇总（质保即将到期数 + 售后待处理 + 返利待结算）。"""
    from .warranty_service import get_urgent_transactions
    from .aftersales_service import get_pending_count as aftersales_pending
    from .rebate_service import get_pending_count as rebate_pending

    urgent = await get_urgent_transactions(db)
    return {
        "warrantyUrgent": len(urgent),
        "afterSalesPending": await aftersales_pending(db),
        "rebatePending": await rebate_pending(db),
    }


# ==================== 提醒生成 ====================

async def check_warranty_reminders(db: AsyncSession) -> list[NotificationRecord]:
    """检查质保到期提醒（BR-8）。返回本次新生成的通知（供前端弹浏览器通知）。"""
    from .warranty_service import get_urgent_transactions
    now = now_utc()
    urgent = await get_urgent_transactions(db)
    created: list[NotificationRecord] = []
    for t in urgent:
        if await _find_today_notification(db, "warranty_expiring", t.id, now):
            continue
        customer = await db.get(Customer, t.customer_id)
        days_left = 0
        if t.warranty_end:
            days_left = (t.warranty_end.replace(tzinfo=None) - now).days
        n = NotificationRecord(
            type="warranty_expiring", ref_id=t.id, title="质保到期提醒",
            content=f"客户{customer.xianyu_nickname if customer else '?'}的订单（{t.product_name}）将在{days_left}天后过保",
            status="unread", scheduled_at=now, sent_at=now, created_at=now,
        )
        db.add(n)
        created.append(n)
    if created:
        await db.flush()
    return created


async def check_customer_recall_reminders(db: AsyncSession) -> list[NotificationRecord]:
    """检查重点客户回访提醒（FR-7.4）。返回新生成的通知。"""
    now = now_utc()
    s = await get_settings(db)
    cutoff = now - timedelta(days=s.recall_days)
    customers = list((await db.execute(
        select(Customer).where(Customer.deleted_at.is_(None), Customer.level.in_(["vip", "core"]))
    )).scalars().all())
    created: list[NotificationRecord] = []
    for c in customers:
        if not c.first_trade_at:
            continue
        # 该客户最近交易
        trades = list((await db.execute(
            select(Transaction).where(
                Transaction.customer_id == c.id, Transaction.deleted_at.is_(None)
            )
        )).scalars().all())
        if not trades:
            continue
        last_trade = max(
            (t.trade_at.replace(tzinfo=None) if t.trade_at and t.trade_at.tzinfo else t.trade_at
             for t in trades if t.trade_at),
            default=None,
        )
        if last_trade is None or last_trade > cutoff:
            continue
        if await _find_today_notification(db, "customer_recall", c.id, now):
            continue
        days_since = (now - last_trade).days
        n = NotificationRecord(
            type="customer_recall", ref_id=c.id, title="客户回访提醒",
            content=f"{'核心' if c.level == 'core' else 'VIP'}客户「{c.xianyu_nickname}」已 {days_since} 天未交易，建议主动回访",
            status="unread", scheduled_at=now, sent_at=now, created_at=now,
        )
        db.add(n)
        created.append(n)
    if created:
        await db.flush()
    return created


async def check_rebate_reminders(db: AsyncSession) -> list[NotificationRecord]:
    """检查待结算返利提醒（FR-7.3）。返回新生成的通知。"""
    from .rebate_service import get_pending_count as rebate_pending
    now = now_utc()
    pending_count = await rebate_pending(db)
    if pending_count == 0:
        return []
    if await _find_today_notification(db, "rebate_pending", None, now):
        return []
    n = NotificationRecord(
        type="rebate_pending", ref_id=None, title="返利结算提醒",
        content=f"当前有 {pending_count} 笔待结算返利，请及时处理",
        status="unread", scheduled_at=now, sent_at=now, created_at=now,
    )
    db.add(n)
    await db.flush()
    return [n]


async def run_all_reminder_checks(db: AsyncSession) -> list[NotificationRecord]:
    """执行所有提醒检查。返回本次新生成的通知（供前端弹浏览器通知）。"""
    created: list[NotificationRecord] = []
    created.extend(await check_warranty_reminders(db))
    created.extend(await check_customer_recall_reminders(db))
    created.extend(await check_rebate_reminders(db))
    return created
