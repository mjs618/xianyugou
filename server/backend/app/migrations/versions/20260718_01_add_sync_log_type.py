"""Add sync_type column to xianyu_sync_logs to distinguish order/item syncs.

Revision ID: 20260718_01
Revises: 20260716_01
Create Date: 2026-07-18

Gap 3 修复：商品同步也写 XianyuSyncLog，需区分订单同步与商品同步。
新增 sync_type 列（order/item），历史记录默认 order。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_01"
down_revision: Union[str, None] = "20260716_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(bind, table: str) -> set[str]:
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table})")
    return {row[1] for row in rows}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, "xianyu_sync_logs")

    with op.batch_alter_table("xianyu_sync_logs") as batch_op:
        if "sync_type" not in existing:
            batch_op.add_column(
                sa.Column("sync_type", sa.String(length=10), nullable=False, server_default="order")
            )


def downgrade() -> None:
    with op.batch_alter_table("xianyu_sync_logs") as batch_op:
        batch_op.drop_column("sync_type")
