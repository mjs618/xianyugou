from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .base import ORMBase


class OperationLogOut(ORMBase):
    id: int
    module: str
    action: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class LogListResponse(BaseModel):
    items: List[OperationLogOut]
    total: int
