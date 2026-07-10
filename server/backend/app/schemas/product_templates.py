from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class ProductTemplateOut(ORMBase):
    id: int
    name: str
    default_cost: float
    default_sale_price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    warranty_days: int
    is_active: bool
    source_xianyu_account_id: Optional[int] = None
    source_xianyu_item_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProductTemplateCreate(BaseModel):
    name: str
    default_cost: float
    default_sale_price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    warranty_days: int = Field(default=30, ge=0)
    is_active: bool = True
    source_xianyu_account_id: Optional[int] = None
    source_xianyu_item_id: Optional[str] = None


class ProductTemplateUpdate(BaseModel):
    name: Optional[str] = None
    default_cost: Optional[float] = None
    default_sale_price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    warranty_days: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    source_xianyu_account_id: Optional[int] = None
    source_xianyu_item_id: Optional[str] = None
