from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class XianyuAccountCreate(BaseModel):
    nickname: str
    cookies: str


class XianyuAccountUpdate(BaseModel):
    nickname: Optional[str] = None
    cookies: Optional[str] = None
    auto_sync_enabled: Optional[bool] = None
    auto_sync_interval_minutes: Optional[int] = Field(default=None, ge=60, le=1440)


class XianyuAccountOut(ORMBase):
    id: int
    nickname: str
    unb: Optional[str] = None
    status: str
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    auto_sync_enabled: bool = False
    auto_sync_interval_minutes: int = 120
    consecutive_failures: int = 0
    paused_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class XianyuAccountTestResult(BaseModel):
    valid: bool
    unb: Optional[str] = None
    message: str


class CookieCloudConfigStatus(BaseModel):
    enabled: bool
    configured_keys: list[str] = []
    missing_keys: list[str] = []
    domain_keyword: str
    message: str
    next_step: str


class XianyuSyncResult(BaseModel):
    success: bool
    fetched: int = 0
    created_count: int = 0
    skipped_count: int = 0
    error: Optional[str] = None


class XianyuItemSyncResult(BaseModel):
    success: bool
    fetched: int = 0
    upserted_count: int = 0
    error: Optional[str] = None


class XianyuItemOut(ORMBase):
    id: int
    account_id: int
    item_id: str
    title: Optional[str] = None
    price: float
    item_status: Optional[str] = None
    image_url: Optional[str] = None
    projected_template_id: Optional[int] = None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class XianyuItemImportRequest(BaseModel):
    mirror_ids: list[int] = Field(default_factory=list)
    default_cost: float = Field(default=0.0, ge=0)
    warranty_days: int = Field(default=30, ge=0)


class XianyuItemImportResult(BaseModel):
    created_count: int = 0
    skipped_count: int = 0


class XianyuOrderOut(ORMBase):
    id: int
    account_id: int
    order_no: str
    order_status: Optional[str] = None
    buyer_nick: Optional[str] = None
    product_name: Optional[str] = None
    sale_price: float
    trade_at: Optional[datetime] = None
    projected_transaction_id: Optional[int] = None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
