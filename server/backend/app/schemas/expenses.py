from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class OperatingExpenseOut(ORMBase):
    id: int
    category: str
    amount: float
    occurred_at: datetime
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OperatingExpenseCreate(BaseModel):
    category: str = Field(default="擦亮", min_length=1, max_length=64)
    amount: float = Field(gt=0)
    occurred_at: datetime
    notes: Optional[str] = None


class OperatingExpenseUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=64)
    amount: Optional[float] = Field(default=None, gt=0)
    occurred_at: Optional[datetime] = None
    notes: Optional[str] = None
