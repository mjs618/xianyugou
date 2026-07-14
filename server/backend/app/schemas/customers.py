from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import ORMBase


class CustomerOut(ORMBase):
    id: int
    xianyu_nickname: str
    contact_info: Optional[str] = None
    first_trade_at: Optional[datetime] = None
    total_spent: float
    trade_count: int
    level: str
    tags: List[str] = []
    is_blacklist: bool
    notes: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class CustomerCreate(BaseModel):
    xianyu_nickname: str
    contact_info: Optional[str] = None
    notes: Optional[str] = None
    is_blacklist: bool = False


class CustomerUpdate(BaseModel):
    """更新客户字段。expected_version 由路由层 pop 出来传给 service 用于乐观并发控制。"""
    model_config = {"extra": "allow"}

    xianyu_nickname: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None
    is_blacklist: Optional[bool] = None
    tags: Optional[List[str]] = None
    expected_version: Optional[int] = None
