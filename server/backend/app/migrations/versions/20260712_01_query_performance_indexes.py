"""Add query performance indexes for finance and notification queries.

Revision ID: 20260712_01
Revises: 20260711_01
Create Date: 2026-07-12

新增两个索引以加速高频查询：
1. ix_transactions_active_trade: 部分索引，仅覆盖活跃交易（未删除、非 closed），
   加速财务统计的范围扫描（trade_at >= start AND trade_at <= end）。
2. ix_notification_records_type_scheduled: 复合索引，加速 _find_today_notification
   去重查询（type = ? AND scheduled_at >= ? AND scheduled_at < ?）。
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260712_01"
down_revision: Union[str, None] = "20260711_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 部分索引：仅索引活跃交易（未删除、非全额退款），加速财务范围查询
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_active_trade "
        "ON transactions (trade_at) "
        "WHERE deleted_at IS NULL AND status != 'closed'"
    )
    # 复合索引：加速通知去重查询（type + scheduled_at 范围）
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notification_records_type_scheduled "
        "ON notification_records (type, scheduled_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notification_records_type_scheduled")
    op.execute("DROP INDEX IF EXISTS ix_transactions_active_trade")
