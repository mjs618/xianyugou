"""返利记录模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RebateRecord(Base):
    """返利记录"""
    __tablename__ = "rebate_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    buyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending/paid/cancelled
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
