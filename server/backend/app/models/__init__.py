"""SQLAlchemy ORM 模型 - 与前端 src/types/index.ts 的 15 个接口一一对应。

设计原则：
- 所有业务表自增主键 ++id
- 软删除统一用 deleted_at（查询时过滤，与前端一致）
- 乐观锁用 version 字段
- 日期时间统一用 DateTime，存储 UTC
- 标签 / 附件等数组字段，SQLite/MySQL 用 JSON 列存储
"""
from .customer import Customer, CustomerLink, CustomerTag, CustomerTagRelation
from .transaction import Transaction, ProductTemplate, WarrantyExtension, OperatingExpense
from .aftersales import AfterSales
from .rebate import RebateRecord
from .notification import NotificationRecord
from .attachment import Attachment
from .mail import MailRecord
from .audit import OperationLog
from .settings import Settings as SettingsModel
# 同时暴露原始类名，供 service 直接 import
from .settings import Settings  # noqa: F401
from .xianyu import XianyuAccount, XianyuItem, XianyuOrder, XianyuSyncLog
from .reply_assistant import ReplyAssistantSettings, ReplyRule

__all__ = [
    "Customer",
    "CustomerLink",
    "CustomerTag",
    "CustomerTagRelation",
    "Transaction",
    "ProductTemplate",
    "WarrantyExtension",
    "OperatingExpense",
    "AfterSales",
    "RebateRecord",
    "NotificationRecord",
    "Attachment",
    "MailRecord",
    "OperationLog",
    "SettingsModel",
    "XianyuAccount",
    "XianyuItem",
    "XianyuOrder",
    "XianyuSyncLog",
    "ReplyAssistantSettings",
    "ReplyRule",
]
