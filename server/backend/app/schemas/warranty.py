"""质保延长请求 schema。"""
from typing import Optional

from pydantic import BaseModel, Field


class WarrantyExtend(BaseModel):
    """延长质保。days 必须 > 0。"""
    model_config = {"extra": "allow"}

    days: int = Field(..., gt=0, description="延长天数，必须大于 0")
    reason: Optional[str] = None


class WarrantyEndEarly(BaseModel):
    """提前结束质保。reason 可选。"""
    model_config = {"extra": "allow"}

    reason: Optional[str] = None
