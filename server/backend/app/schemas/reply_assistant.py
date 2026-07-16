"""回复助手 API 契约。"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .base import ORMBase


class ReplyAssistantSettingsOut(BaseModel):
    id: int
    enabled: bool
    ai_enabled: bool
    api_base_url: str
    api_key_configured: bool
    model: str
    system_prompt: str


class ReplyAssistantSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    ai_enabled: Optional[bool] = None
    api_base_url: Optional[str] = Field(default=None, max_length=512)
    api_key: Optional[str] = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    model: Optional[str] = Field(default=None, max_length=100)
    system_prompt: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def reject_explicit_null(self):
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class ReplyRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    priority: int = Field(default=0, ge=-1000, le=1000)
    keywords: list[str] = Field(min_length=1, max_length=20)
    reply_text: str = Field(min_length=1, max_length=1000)
    product_template_id: Optional[int] = None


class ReplyRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=-1000, le=1000)
    keywords: Optional[list[str]] = Field(default=None, min_length=1, max_length=20)
    reply_text: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    product_template_id: Optional[int] = None

    @model_validator(mode="after")
    def reject_invalid_null(self):
        for field_name in self.model_fields_set - {"product_template_id"}:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class ReplyRuleOut(ORMBase):
    id: int
    name: str
    enabled: bool
    priority: int
    keywords: list[str]
    reply_text: str
    product_template_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ReplyContextMessage(BaseModel):
    role: Literal["user", "seller"]
    content: str = Field(min_length=1, max_length=1000)


class ReplySuggestionRequest(BaseModel):
    account_id: int
    product_template_id: Optional[int] = None
    buyer_message: str = Field(min_length=1, max_length=2000)
    context_messages: list[ReplyContextMessage] = Field(
        default_factory=list, max_length=10
    )


class ReplySuggestionOut(BaseModel):
    reply: str
    source: Literal["rule", "ai"]
    matched_rule_id: Optional[int] = None
    risk_level: Literal["normal", "manual_required"]
    risk_reasons: list[str]
    copy_allowed: bool = True
