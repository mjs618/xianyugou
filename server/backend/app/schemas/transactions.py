from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import ORMBase


class TransactionOut(ORMBase):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    xianyu_order_no: Optional[str] = None
    product_name: str
    product_template_id: Optional[int] = None
    sale_price: float
    cost_price: float
    profit: float
    trade_at: datetime
    shipped_at: Optional[datetime] = None
    status: str
    warranty_end: Optional[datetime] = None
    warranty_days: int
    source_type: str
    channel: str = "xianyu"
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: List[str] = []
    version: int
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    customer_id: int
    xianyu_order_no: Optional[str] = None
    product_name: str
    product_template_id: Optional[int] = None
    sale_price: float
    cost_price: float
    trade_at: datetime
    shipped_at: Optional[datetime] = None
    status: str = "pending"
    warranty_days: Optional[int] = None
    source_type: str = "direct"
    channel: str = "xianyu"
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None


class TransactionUpdate(BaseModel):
    """更新交易字段。所有字段可选，仅传需要修改的字段。
    expected_version 由路由层 pop 出来传给 service 用于乐观并发控制。
    """
    model_config = {"extra": "allow"}

    customer_id: Optional[int] = None
    xianyu_order_no: Optional[str] = None
    product_name: Optional[str] = None
    product_template_id: Optional[int] = None
    sale_price: Optional[float] = None
    cost_price: Optional[float] = None
    trade_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    status: Optional[str] = None
    warranty_days: Optional[int] = None
    source_type: Optional[str] = None
    channel: Optional[str] = None
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None
    expected_version: Optional[int] = None


class StatusChange(BaseModel):
    """变更交易状态。expected_version 可选，用于乐观并发控制。"""
    model_config = {"extra": "allow"}

    status: str
    expected_version: Optional[int] = None
