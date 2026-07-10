"""Public Pydantic schema facade grouped by domain modules."""
from .base import ORMBase
from .customers import CustomerCreate, CustomerOut, CustomerUpdate
from .transactions import (
    StatusChange,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from .aftersales import AfterSalesCreate, AfterSalesOut, AfterSalesUpdate
from .rebates import RebateBatchPay, RebateOut, RebateStatusChange
from .expenses import (
    OperatingExpenseCreate,
    OperatingExpenseOut,
    OperatingExpenseUpdate,
)
from .product_templates import (
    ProductTemplateCreate,
    ProductTemplateOut,
    ProductTemplateUpdate,
)
from .settings import SettingsOut, SettingsUpdate
from .audit import LogListResponse, OperationLogOut
from .migrate import MigrateImportResponse
from .attachments import AttachmentBatchRequest, AttachmentOut
from .xianyu import (
    CookieCloudConfigStatus,
    XianyuAccountCreate,
    XianyuAccountOut,
    XianyuAccountTestResult,
    XianyuAccountUpdate,
    XianyuItemImportRequest,
    XianyuItemImportResult,
    XianyuItemOut,
    XianyuItemSyncResult,
    XianyuOrderOut,
    XianyuSyncResult,
)
from .common import HealthResponse, MessageResponse


__all__ = [
    "ORMBase",
    "CustomerOut",
    "CustomerCreate",
    "CustomerUpdate",
    "TransactionOut",
    "TransactionCreate",
    "TransactionUpdate",
    "StatusChange",
    "AfterSalesOut",
    "AfterSalesCreate",
    "AfterSalesUpdate",
    "RebateOut",
    "RebateStatusChange",
    "RebateBatchPay",
    "OperatingExpenseOut",
    "OperatingExpenseCreate",
    "OperatingExpenseUpdate",
    "ProductTemplateOut",
    "ProductTemplateCreate",
    "ProductTemplateUpdate",
    "SettingsOut",
    "SettingsUpdate",
    "OperationLogOut",
    "LogListResponse",
    "MigrateImportResponse",
    "AttachmentOut",
    "AttachmentBatchRequest",
    "XianyuAccountCreate",
    "XianyuAccountUpdate",
    "XianyuAccountOut",
    "XianyuAccountTestResult",
    "CookieCloudConfigStatus",
    "XianyuSyncResult",
    "XianyuItemSyncResult",
    "XianyuItemOut",
    "XianyuItemImportRequest",
    "XianyuItemImportResult",
    "XianyuOrderOut",
    "MessageResponse",
    "HealthResponse",
]
