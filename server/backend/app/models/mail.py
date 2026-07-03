"""邮件发送记录模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class MailRecord(Base):
    """邮件发送记录。gpt_password / email_password 为敏感字段，写入时加密。"""
    __tablename__ = "mail_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    to: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_account: Mapped[str] = mapped_column(String(255), nullable=False)
    gpt_password: Mapped[str] = mapped_column(String(512), nullable=False)  # 加密存储
    token_url: Mapped[str] = mapped_column(String(512), nullable=False)
    email_password: Mapped[str] = mapped_column(String(512), nullable=False)  # 加密存储
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)  # success/failed
    error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
