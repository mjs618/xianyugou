"""Reconcile indexes omitted by legacy SQLite ALTER TABLE migrations.

Revision ID: 20260710_02
Revises: 20260710_01
Create Date: 2026-07-10
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260710_02"
down_revision: Union[str, None] = "20260710_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_product_templates_source_xianyu_account_id "
        "ON product_templates (source_xianyu_account_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_product_templates_source_xianyu_item_id "
        "ON product_templates (source_xianyu_item_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_shipped_at "
        "ON transactions (shipped_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transactions_shipped_at")
    op.execute("DROP INDEX IF EXISTS ix_product_templates_source_xianyu_item_id")
    op.execute("DROP INDEX IF EXISTS ix_product_templates_source_xianyu_account_id")
