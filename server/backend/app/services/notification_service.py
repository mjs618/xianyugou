"""通知服务 - 复刻前端 notificationService.ts。

迁移分工：
- 通知 CRUD + pending-summary + 提醒生成：后端实现
- 浏览器通知权限/弹窗：留前端（new Notification 是浏览器能力）

性能优化：
- _find_today_notification 使用范围查询（scheduled_at >= day_start AND < day_end）替代 func.date() 以利用索引
- 提醒检查使用批量加载消除 N+1 查询
- get_pending_summary 使用 COUNT 查询替代加载完整对象
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AfterSales, NotificationRecord, Customer, Transaction
from ..utils.helpers import now_utc
from .settings_service import get_settings


async def _find_today_notification(
    db: AsyncSession, ntype: str, ref_id: Optional[int], now: datetime
) -> Optional[NotificationRecord]:
    """防重：查找当天同类型同 ref 的通知。

    使用范围查询（scheduled_at >= day_start AND < day_end）替代 func.date()，
    以利用 scheduled_at 索引。
    """
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    stmt = select(NotificationRecord).where(
        NotificationRecord.type == ntype,
        NotificationRecord.scheduled_at >= day_start,
        NotificationRecord.scheduled_at < day_end,
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
    """标记单条通知为已读。不存在时抛 ValueError（路由返回 404，
    对齐 mail_record/product_template 等 delete 不存在资源的行为）。"""
    n = await db.get(NotificationRecord, nid)
    if n is None:
        raise ValueError("通知不存在")
    n.status = "read"


async def mark_all_as_read(db: AsyncSession) -> None:
    await db.execute(
        update(NotificationRecord).where(NotificationRecord.status == "unread").values(status="read")
    )


async def dismiss(db: AsyncSession, nid: int) -> None:
    """忽略单条通知。不存在时抛 ValueError（路由返回 404）。"""
    n = await db.get(NotificationRecord, nid)
    if n is None:
        raise ValueError("通知不存在")
    n.status = "dismissed"


async def get_pending_summary(db: AsyncSession) -> dict:
    """待处理事项汇总（质保即将到期数 + 售后待处理 + 返利待结算）。"""
    from .warranty_service import count_urgent_transactions
    from .aftersales_service import get_pending_count as aftersales_pending
    from .rebate_service import get_pending_count as rebate_pending

    urgent_count = await count_urgent_transactions(db)
    return {
        "warrantyUrgent": urgent_count,
        "afterSalesPending": await aftersales_pending(db),
        "rebatePending": await rebate_pending(db),
    }


# ==================== 提醒生成 ====================

async def check_warranty_reminders(db: AsyncSession) -> list[NotificationRecord]:
    """检查质保到期提醒（BR-8）。返回本次新生成的通知（供前端弹浏览器通知）。"""
    from .warranty_service import get_urgent_transactions
    now = now_utc()
    urgent = await get_urgent_transactions(db)

    # 批量加载所有相关客户，消除循环内 N+1 查询
    customer_ids = {t.customer_id for t in urgent if t.customer_id}
    customers_map: dict[int, Customer] = {}
    if customer_ids:
        rows = (await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )).scalars().all()
        customers_map = {c.id: c for c in rows}

    created: list[NotificationRecord] = []
    for t in urgent:
        if await _find_today_notification(db, "warranty_expiring", t.id, now):
            continue
        customer = customers_map.get(t.customer_id)
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

    # 单条 SQL 聚合每个客户最近交易时间，消除循环内 N+1 查询
    customer_ids = [c.id for c in customers if c.first_trade_at]
    last_trade_map: dict[int, datetime] = {}
    if customer_ids:
        rows = (await db.execute(
            select(
                Transaction.customer_id.label("cid"),
                func.max(Transaction.trade_at).label("last_trade"),
            ).where(
                Transaction.customer_id.in_(customer_ids),
                Transaction.deleted_at.is_(None),
            ).group_by(Transaction.customer_id)
        )).all()
        last_trade_map = {r.cid: r.last_trade for r in rows}

    created: list[NotificationRecord] = []
    for c in customers:
        if not c.first_trade_at:
            continue
        last_trade = last_trade_map.get(c.id)
        if last_trade is None:
            continue
        last_trade_naive = last_trade.replace(tzinfo=None) if last_trade and last_trade.tzinfo else last_trade
        if last_trade_naive > cutoff:
            continue
        if await _find_today_notification(db, "customer_recall", c.id, now):
            continue
        days_since = (now - last_trade_naive).days
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


async def check_aftersales_followup_reminders(db: AsyncSession) -> list[NotificationRecord]:
    """检查售后跟进提醒：待处理超过 24 小时、处理中超过 48 小时。"""
    now = now_utc()
    stmt = select(AfterSales).where(
        AfterSales.deleted_at.is_(None),
        AfterSales.status.in_(["pending", "processing"]),
    )
    tickets = list((await db.execute(stmt)).scalars().all())

    # 批量加载所有相关交易和客户，消除循环内 N+1 查询
    tx_ids = {t.transaction_id for t in tickets if t.transaction_id}
    txs_map: dict[int, Transaction] = {}
    customers_map: dict[int, Customer] = {}
    if tx_ids:
        tx_rows = (await db.execute(
            select(Transaction).where(Transaction.id.in_(tx_ids))
        )).scalars().all()
        txs_map = {t.id: t for t in tx_rows}
        customer_ids = {t.customer_id for t in tx_rows if t.customer_id}
        if customer_ids:
            cust_rows = (await db.execute(
                select(Customer).where(Customer.id.in_(customer_ids))
            )).scalars().all()
            customers_map = {c.id: c for c in cust_rows}

    created: list[NotificationRecord] = []
    for ticket in tickets:
        if not ticket.created_at:
            continue
        created_at = ticket.created_at.replace(tzinfo=None) if ticket.created_at.tzinfo else ticket.created_at
        elapsed_hours = int((now - created_at).total_seconds() // 3600)
        threshold = 24 if ticket.status == "pending" else 48
        if elapsed_hours <= threshold:
            continue
        if await _find_today_notification(db, "aftersales_pending", ticket.id, now):
            continue

        tx = txs_map.get(ticket.transaction_id)
        customer = customers_map.get(tx.customer_id) if tx else None
        status_text = "待处理" if ticket.status == "pending" else "处理中"
        title = "售后跟进提醒"
        content = (
            f"{status_text}工单 #{ticket.id} 已超过 {threshold} 小时未完成"
            f"（{customer.xianyu_nickname if customer else '未知客户'} / {tx.product_name if tx else '未知交易'}），请及时跟进"
        )
        n = NotificationRecord(
            type="aftersales_pending",
            ref_id=ticket.id,
            title=title,
            content=content,
            status="unread",
            scheduled_at=now,
            sent_at=now,
            created_at=now,
        )
        db.add(n)
        created.append(n)
    if created:
        await db.flush()
    return created


async def run_all_reminder_checks(db: AsyncSession) -> list[NotificationRecord]:
    """执行所有提醒检查。返回本次新生成的通知（供前端弹浏览器通知）。"""
    created: list[NotificationRecord] = []
    created.extend(await check_warranty_reminders(db))
    created.extend(await check_aftersales_followup_reminders(db))
    created.extend(await check_customer_recall_reminders(db))
    created.extend(await check_rebate_reminders(db))
    return created


# ==================== 熔断/恢复告警 ====================

async def create_account_paused_notification(
    db: AsyncSession, account_id: int, account_nickname: str, reason: str
) -> Optional[NotificationRecord]:
    """账号熔断时创建告警通知（当天同账号去重）。

    对应设计文档 P3「告警」：风控响应出现后通知用户。
    """
    now = now_utc()
    if await _find_today_notification(db, "account_paused", account_id, now):
        return None
    n = NotificationRecord(
        type="account_paused",
        ref_id=account_id,
        title="账号已熔断",
        content=f"账号「{account_nickname}」因{reason}已触发熔断，自动同步已暂停。请更新 Cookie 并手动恢复。",
        status="unread",
        scheduled_at=now,
        sent_at=now,
        created_at=now,
    )
    db.add(n)
    await db.flush()
    return n


async def create_account_recovered_notification(
    db: AsyncSession, account_id: int, account_nickname: str
) -> Optional[NotificationRecord]:
    """账号从熔断恢复时创建通知（当天同账号去重）。"""
    now = now_utc()
    if await _find_today_notification(db, "account_recovered", account_id, now):
        return None
    n = NotificationRecord(
        type="account_recovered",
        ref_id=account_id,
        title="账号已恢复",
        content=f"账号「{account_nickname}」已恢复在线，自动同步将在下个周期继续。",
        status="unread",
        scheduled_at=now,
        sent_at=now,
        created_at=now,
    )
    db.add(n)
    await db.flush()
    return n
