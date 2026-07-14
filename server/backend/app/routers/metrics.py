"""P1-3 修复：监控指标路由。

GET /api/metrics：聚合账号状态、同步、备份、通知等运维关键指标。
需 X-API-Token 认证（不在白名单中），避免业务指标外泄。
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import NotificationRecord, XianyuAccount, XianyuSyncLog
from ..schemas.metrics import (
    AccountMetrics,
    BackupMetrics,
    MetricsResponse,
    SyncMetrics,
)
from ..utils.helpers import now_utc

router = APIRouter(prefix="/api/metrics", tags=["system"])


@router.get("", response_model=MetricsResponse)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """返回业务监控指标 JSON。

    覆盖：
    - 账号状态统计（total/online/paused/invalid）
    - 近 24 小时同步统计（成功/失败次数、拉取订单数、新建交易数）
    - 数据库备份状态（最近备份时间、备份文件数）
    - 通知未读数
    - 同步调度器运行状态
    """
    now = now_utc()
    since_24h = now - timedelta(hours=24)

    # 1. 账号状态统计（兼容 P2-3 软删除字段：仅在模型存在时过滤）
    account_query = select(XianyuAccount.status, func.count()).group_by(XianyuAccount.status)
    # P2-3 软删除字段：模型存在 deleted_at 时过滤已删除账号
    if hasattr(XianyuAccount, "deleted_at"):
        account_query = account_query.where(XianyuAccount.deleted_at.is_(None))
    account_status_rows = (await db.execute(account_query)).all()
    status_counts = {s: c for s, c in account_status_rows}
    total_accounts = sum(status_counts.values())
    accounts = AccountMetrics(
        total=total_accounts,
        online=status_counts.get("online", 0),
        paused=status_counts.get("paused", 0),
        invalid=status_counts.get("invalid", 0),
    )

    # 2. 近 24h 同步日志聚合（按 status 分组）
    sync_rows = (await db.execute(
        select(
            XianyuSyncLog.status,
            func.count(),
            func.sum(XianyuSyncLog.fetched),
            func.sum(XianyuSyncLog.created_count),
        )
        .where(XianyuSyncLog.created_at >= since_24h)
        .group_by(XianyuSyncLog.status)
    )).all()
    sync_by_status = {r[0]: r for r in sync_rows}
    success_row = sync_by_status.get("success")
    failed_row = sync_by_status.get("failed")
    sync = SyncMetrics(
        last_24h_success=success_row[1] if success_row else 0,
        last_24h_failed=failed_row[1] if failed_row else 0,
        last_24h_fetched_orders=int(success_row[2] or 0) if success_row else 0,
        last_24h_created_transactions=int(success_row[3] or 0) if success_row else 0,
    )

    # 3. 最近一次同步日志（不论成功/失败）
    last_log = (await db.execute(
        select(XianyuSyncLog)
        .order_by(XianyuSyncLog.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if last_log is not None:
        sync.last_error = last_log.error
        sync.last_sync_at = last_log.created_at

    # 4. 备份指标（扫目录最新文件）
    from ..maintenance.backup_scheduler import scheduler as backup_scheduler
    backup = BackupMetrics(
        last_backup_at=backup_scheduler._last_backup_at(),
        backup_count=backup_scheduler._count_backups(),
        backup_dir_exists=backup_scheduler._backup_dir.exists(),
    )

    # 5. 通知未读数
    unread = (await db.execute(
        select(func.count(NotificationRecord.id)).where(NotificationRecord.status == "unread")
    )).scalar() or 0

    # 6. 调度器状态
    from ..services.sync_scheduler import scheduler as sync_scheduler
    scheduler_running = sync_scheduler.running

    return MetricsResponse(
        timestamp=datetime.now(timezone.utc),
        accounts=accounts,
        sync=sync,
        backup=backup,
        notifications_unread=unread,
        scheduler_running=scheduler_running,
    )
