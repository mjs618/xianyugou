"""交易相关模型：Transaction / ProductTemplate / WarrantyExtension"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, Float, Integer, String, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from ..database import Base
from .base import TimestampMixin


class ProductTemplate(TimestampMixin, Base):
    """商品模板"""
    __tablename__ = "product_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    default_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    default_sale_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    warranty_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Transaction(TimestampMixin, Base):
    """交易记录"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    xianyu_order_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sale_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trade_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending/completed/aftersales/closed
    warranty_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    warranty_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")  # direct/introduced/repeat
    source_customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class WarrantyExtension(Base):
    """质保延长记录"""
    __tablename__ = "warranty_extensions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    old_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    new_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extended_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
