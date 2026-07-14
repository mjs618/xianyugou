"""客户标签相关请求 schema。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class CustomerTagCreate(BaseModel):
    """创建标签。"""
    model_config = {"extra": "allow"}

    name: str = Field(..., min_length=1, description="标签名")
    color: Optional[str] = None


class CustomerTagsUpdate(BaseModel):
    """设置客户标签（替换语义）。"""
    model_config = {"extra": "allow"}

    tags: List[str] = Field(default_factory=list, description="标签名列表")
