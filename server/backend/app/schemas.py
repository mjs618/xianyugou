"""Pydantic 请求/响应模型。

统一用 model_config = ConfigDict(from_attributes=True) 以支持从 ORM 对象直接序列化。
日期字段用 datetime，FastAPI 默认序列化为 ISO 字符串（与前端 dayjs 兼容）。
"""
from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ==================== 客户 ====================
class CustomerOut(ORMBase):
    id: int
    xianyu_nickname: str
    contact_info: Optional[str] = None
    first_trade_at: Optional[datetime] = None
    total_spent: float
    trade_count: int
    level: str
    tags: List[str] = []
    is_blacklist: bool
    notes: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class CustomerCreate(BaseModel):
    xianyu_nickname: str
    contact_info: Optional[str] = None
    notes: Optional[str] = None
    is_blacklist: bool = False


class CustomerUpdate(BaseModel):
    xianyu_nickname: Optional[str] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None
    is_blacklist: Optional[bool] = None
    tags: Optional[List[str]] = None


# ==================== 交易 ====================
class TransactionOut(ORMBase):
    id: int
    customer_id: int
    customer_name: Optional[str] = None  # 列表查询时内联返回（详情/单查可为空）
    xianyu_order_no: Optional[str] = None
    product_name: str
    product_template_id: Optional[int] = None
    sale_price: float
    cost_price: float
    profit: float
    trade_at: datetime
    shipped_at: Optional[datetime] = None
    status: str
    warranty_end: Optional[datetime] = None
    warranty_days: int
    source_type: str
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: List[str] = []
    version: int
    created_at: datetime
    updated_at: datetime


class TransactionCreate(BaseModel):
    customer_id: int
    xianyu_order_no: Optional[str] = None
    product_name: str
    product_template_id: Optional[int] = None
    sale_price: float
    cost_price: float
    trade_at: datetime
    shipped_at: Optional[datetime] = None
    status: str = "pending"
    warranty_days: Optional[int] = None
    source_type: str = "direct"
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None


class TransactionUpdate(BaseModel):
    xianyu_order_no: Optional[str] = None
    product_name: Optional[str] = None
    product_template_id: Optional[int] = None
    sale_price: Optional[float] = None
    cost_price: Optional[float] = None
    trade_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    status: Optional[str] = None
    warranty_days: Optional[int] = None
    source_type: Optional[str] = None
    source_customer_id: Optional[int] = None
    notes: Optional[str] = None
    attachments: Optional[List[str]] = None


class StatusChange(BaseModel):
    status: str


# ==================== 售后 ====================
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


# ==================== 返利 ====================
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


# ==================== 运营支出 ====================
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


# ==================== 商品模板 ====================
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


# ==================== 设置 ====================
class SettingsOut(ORMBase):
    id: int
    warranty_days: int
    rebate_rate: float
    rebate_base: str
    vip_threshold: float
    core_threshold: float
    vip_trade_count: int
    core_trade_count: int
    recall_days: int
    backup_path: Optional[str] = None
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_from: Optional[str] = None


class SettingsUpdate(BaseModel):
    warranty_days: Optional[int] = None
    rebate_rate: Optional[float] = None
    rebate_base: Optional[str] = None
    vip_threshold: Optional[float] = None
    core_threshold: Optional[float] = None
    vip_trade_count: Optional[int] = None
    core_trade_count: Optional[int] = None
    recall_days: Optional[int] = None
    backup_path: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_from: Optional[str] = None


# ==================== 审计日志 ====================
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


# ==================== 迁移 ====================
class MigrateImportResponse(BaseModel):
    success: bool = True
    counts: dict
    message: str = "导入成功"


# ==================== 闲鱼账号（第二阶段） ====================
class XianyuAccountCreate(BaseModel):
    nickname: str
    cookies: str


class XianyuAccountUpdate(BaseModel):
    nickname: Optional[str] = None
    cookies: Optional[str] = None


class XianyuAccountOut(ORMBase):
    id: int
    nickname: str
    unb: Optional[str] = None
    status: str
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
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


# ==================== 通用 ====================
class MessageResponse(BaseModel):
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "xianyu-backend"
    time: str
    version: str = "1.0.0"
