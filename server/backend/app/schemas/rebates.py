from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import ORMBase


class RebateOut(ORMBase):
    id: int
    referrer_id: int
    buyer_id: int
    transaction_id: int
    amount: float
    rate: float
    status: str
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class RebateStatusChange(BaseModel):
    status: str
    notes: Optional[str] = None


class RebateBatchPay(BaseModel):
    ids: List[int]
