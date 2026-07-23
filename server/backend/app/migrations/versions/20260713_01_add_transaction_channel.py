"""Add channel column to transactions for sales channel tracking (xianyu/wechat/other).

Revision ID: 20260713_01
Revises: 20260712_01
Create Date: 2026-07-13

为 transactions 表新增 channel 字段（销售渠道：xianyu/wechat/other），
用于区分闲鱼同步订单与微信等其他渠道直接成交的订单，支持财务报表按渠道拆分。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_01"
down_revision: Union[str, None] = "20260712_01"
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
    existing = _existing_columns(bind, "transactions")

    with op.batch_alter_table("transactions") as batch_op:
        if "channel" not in existing:
            batch_op.add_column(
                sa.Column(
                    "channel",
                    sa.String(length=20),
                    nullable=False,
                    server_default="xianyu",
                )
            )

    # 渠道维度聚合索引（幂等）
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_channel "
        "ON transactions (channel)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_channel")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("channel")
