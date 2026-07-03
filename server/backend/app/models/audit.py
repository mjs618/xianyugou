"""操作审计日志模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class OperationLog(Base):
    """操作审计日志。module 见 AuditModule 枚举。"""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # transaction/customer/aftersales/rebate/settings/mail/warranty/system/order
    module: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    target_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
