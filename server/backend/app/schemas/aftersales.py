from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import ORMBase


class AfterSalesOut(ORMBase):
    id: int
    transaction_id: int
    issue_desc: str
    status: str
    solution_type: Optional[str] = None
    solution_desc: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    duration_hours: Optional[int] = None
    attachments: List[str] = []
    original_transaction_status: Optional[str] = None
    deleted_at: Optional[datetime] = None


class AfterSalesCreate(BaseModel):
    transaction_id: int
    issue_desc: str
    attachments: Optional[List[str]] = None


class AfterSalesUpdate(BaseModel):
    status: str
    solution_type: Optional[str] = None
    solution_desc: Optional[str] = None
