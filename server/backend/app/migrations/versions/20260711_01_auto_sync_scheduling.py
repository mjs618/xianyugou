"""Add P3 safe auto-sync scheduling fields to xianyu_accounts.

Revision ID: 20260711_01
Revises: 20260710_02
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260711_01"
down_revision: Union[str, None] = "20260710_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(bind, table: str) -> set[str]:
    """返回 SQLite 表中已存在的列名集合，用于幂等 ADD COLUMN。"""
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table})")
    return {row[1] for row in rows}


def upgrade() -> None:
    # 幂等处理：adopt_existing_database 会先用 Base.metadata.create_all 建表
    # （此时模型已包含新列），再 stamp 旧 baseline 并升级到 head，导致 ADD COLUMN
    # 重复。此处先检查列是否已存在，避免重复添加。
    bind = op.get_bind()
    existing = _existing_columns(bind, "xianyu_accounts")

    with op.batch_alter_table("xianyu_accounts") as batch_op:
        if "auto_sync_enabled" not in existing:
            batch_op.add_column(
                sa.Column(
                    "auto_sync_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "auto_sync_interval_minutes" not in existing:
            batch_op.add_column(
                sa.Column(
                    "auto_sync_interval_minutes",
                    sa.Integer(),
                    nullable=False,
                    server_default="120",
                )
            )
        if "consecutive_failures" not in existing:
            batch_op.add_column(
                sa.Column(
                    "consecutive_failures",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "paused_at" not in existing:
            batch_op.add_column(sa.Column("paused_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("xianyu_accounts") as batch_op:
        batch_op.drop_column("paused_at")
        batch_op.drop_column("consecutive_failures")
        batch_op.drop_column("auto_sync_interval_minutes")
        batch_op.drop_column("auto_sync_enabled")
