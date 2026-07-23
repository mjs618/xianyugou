"""P1-3 修复：监控指标 schema。

聚合账号状态、订单同步、备份、通知等业务运维指标，
供前端 Dashboard 或外部监控系统（Prometheus/Grafana 拉取）使用。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountMetrics(BaseModel):
    """闲鱼账号状态统计。"""
    total: int
    online: int
    paused: int
    invalid: int


class SyncMetrics(BaseModel):
    """近 24 小时订单同步统计。"""
    last_24h_success: int
    last_24h_failed: int
    last_24h_fetched_orders: int
    last_24h_created_transactions: int
    last_error: Optional[str] = None
    last_sync_at: Optional[datetime] = None


class BackupMetrics(BaseModel):
    """数据库备份状态。"""
    last_backup_at: Optional[datetime] = None
    backup_count: int = 0
    backup_dir_exists: bool = False


class MetricsResponse(BaseModel):
    """业务监控指标聚合视图。"""
    timestamp: datetime
    accounts: AccountMetrics
    sync: SyncMetrics
    backup: BackupMetrics
    notifications_unread: int
    scheduler_running: bool
