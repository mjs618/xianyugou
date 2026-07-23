from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from .base import ORMBase


class AttachmentOut(ORMBase):
    id: int
    name: str
    type: str
    size: int
    created_at: datetime


class AttachmentBatchRequest(BaseModel):
    ids: List[int] = Field(default_factory=list, max_length=50)
