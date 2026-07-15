"""回复助手配置与固定回复规则。"""
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import TimestampMixin


class ReplyAssistantSettings(TimestampMixin, Base):
    """回复助手单例配置（固定 id=1）。"""

    __tablename__ = "reply_assistant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    api_base_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=""
    )
    api_key: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    system_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )


class ReplyRule(TimestampMixin, Base):
    """关键词固定回复；商品专属规则优先于通用规则。"""

    __tablename__ = "reply_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", index=True
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", index=True
    )
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    product_template_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_templates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
