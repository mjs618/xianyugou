"""售后工单模型"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, Integer, String, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from ..database import Base


class AfterSales(Base):
    """售后工单"""
    __tablename__ = "after_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    issue_desc: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending/processing/resolved/closed
    solution_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # remote/reship/refund/other
    solution_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attachments: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    # 创建工单时交易的原始状态，用于工单关闭后正确恢复（与前端 P-20 修复对齐）
    original_transaction_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
