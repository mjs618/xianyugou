"""Add deleted_at column to xianyu_accounts for soft delete.

Revision ID: 20260713_02
Revises: 20260713_01
Create Date: 2026-07-13

P2-3 修复：账号删除改为软删除（设置 deleted_at），保留关联数据可追溯。
list_accounts 过滤已删除；sync_scheduler 跳过已删除；所有写操作校验 deleted_at。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_02"
down_revision: Union[str, None] = "20260713_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(bind, table: str) -> set[str]:
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table})")
    return {row[1] for row in rows}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, "xianyu_accounts")

    with op.batch_alter_table("xianyu_accounts") as batch_op:
        if "deleted_at" not in existing:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_xianyu_accounts_deleted_at "
        "ON xianyu_accounts (deleted_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_xianyu_accounts_deleted_at")
    with op.batch_alter_table("xianyu_accounts") as batch_op:
        batch_op.drop_column("deleted_at")
