"""客户相关模型：Customer / CustomerLink / CustomerTag / CustomerTagRelation"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, Float, Integer, String, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from ..database import Base
from .base import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    xianyu_nickname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_spent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", index=True)  # normal/vip/core
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    is_blacklist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class CustomerLink(Base):
    """客户推荐关系：A(referrer) 介绍了 B(buyer)"""
    __tablename__ = "customer_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    buyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class CustomerTag(Base):
    """客户标签定义"""
    __tablename__ = "customer_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class CustomerTagRelation(Base):
    """客户-标签 多对多关联"""
    __tablename__ = "customer_tag_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer_tags.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
