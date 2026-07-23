"""Add reply assistant settings and rules.

Revision ID: 20260716_01
Revises: 20260713_02
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_01"
down_revision: Union[str, None] = "20260713_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "reply_assistant_settings" not in existing_tables:
        op.create_table(
            "reply_assistant_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("ai_enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("api_base_url", sa.String(length=512), server_default="", nullable=False),
            sa.Column("api_key", sa.Text(), server_default="", nullable=False),
            sa.Column("model", sa.String(length=100), server_default="", nullable=False),
            sa.Column("system_prompt", sa.Text(), server_default="", nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "reply_rules" not in existing_tables:
        op.create_table(
            "reply_rules",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
            sa.Column("keywords", sa.JSON(), nullable=False),
            sa.Column("reply_text", sa.Text(), nullable=False),
            sa.Column("product_template_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(
                ["product_template_id"], ["product_templates.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reply_rules_enabled ON reply_rules (enabled)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reply_rules_priority ON reply_rules (priority)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reply_rules_product_template_id "
        "ON reply_rules (product_template_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reply_rules_product_template_id")
    op.execute("DROP INDEX IF EXISTS ix_reply_rules_priority")
    op.execute("DROP INDEX IF EXISTS ix_reply_rules_enabled")
    op.drop_table("reply_rules")
    op.drop_table("reply_assistant_settings")
