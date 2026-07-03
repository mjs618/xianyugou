"""数据迁移服务 - 兼容前端 export.ts 的 JSON 备份格式。

import 备份：清空后批量写入（敏感字段导入为明文，由写入逻辑加密）。
export 备份：导出明文，敏感字段解密（与前端 exportJSON 口径一致）。

备份 data 结构（13 个键）：
customers, transactions, customer_links, after_sales, rebate_records,
product_templates, settings, customer_tags, customer_tag_relations,
warranty_extensions, notification_records, attachments, mail_records
"""
import base64
from datetime import date, datetime
from typing import Any
from sqlalchemy import delete, select, DateTime, Date
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Customer, CustomerLink, CustomerTag, CustomerTagRelation,
    Transaction, ProductTemplate, WarrantyExtension, AfterSales,
    RebateRecord, NotificationRecord, Attachment, MailRecord, Settings as SettingsModel,
)
from ..utils.crypto import encrypt_field, decrypt_field, is_encrypted
from ..utils.helpers import DEFAULT_SETTINGS, parse_date


def _model_date_cols(model: type) -> set[str]:
    """返回模型中所有 DateTime / Date 列名，用于自动转换字符串为日期。"""
    cols = set()
    for col in model.__table__.columns:
        if isinstance(col.type, (DateTime, Date)):
            cols.add(col.name)
    return cols


async def _clear_all(db: AsyncSession) -> None:
    """清空所有业务表（保留表结构）"""
    for model in [
        CustomerTagRelation, CustomerTag, NotificationRecord, WarrantyExtension,
        RebateRecord, AfterSales, CustomerLink, Transaction, ProductTemplate,
        Attachment, MailRecord, Customer, SettingsModel,
    ]:
        await db.execute(delete(model))


def _clean_record(record: dict, model: type, allowed_keys: set[str]) -> dict:
    """保留允许的列，并自动把日期列从字符串/timestamp 转为 datetime。

    基于模型列类型自动检测日期列，避免遗漏（如 settings 的 created_at）。
    """
    date_keys = _model_date_cols(model)
    out = {}
    for k in allowed_keys:
        if k in record and record[k] is not None:
            v = record[k]
            if k in date_keys and not isinstance(v, (datetime, date)):
                v = parse_date(v)
            if v is not None:
                out[k] = v
        elif k in record:
            # 显式 None 也保留（如 deleted_at=None）
            out[k] = None
    return out


# 每张表：允许的列 + 日期列。id 保留（按原 id 导入，保证外键引用不断裂）
CUSTOMER_COLS = {
    "id","xianyu_nickname","contact_info","first_trade_at","total_spent","trade_count",
    "level","tags","is_blacklist","notes","version","created_at","updated_at","deleted_at",
}
CUSTOMER_DATE = {"first_trade_at","created_at","updated_at","deleted_at"}

TRANSACTION_COLS = {
    "id","customer_id","xianyu_order_no","product_name","product_template_id","sale_price",
    "cost_price","profit","trade_at","status","warranty_end","warranty_days","source_type",
    "source_customer_id","notes","attachments","version","created_at","updated_at","deleted_at",
}
TRANSACTION_DATE = {"trade_at","warranty_end","created_at","updated_at","deleted_at"}

LINK_COLS = {"id","referrer_id","buyer_id","transaction_id","level","created_at"}
LINK_DATE = {"created_at"}

AFTERSALES_COLS = {
    "id","transaction_id","issue_desc","status","solution_type","solution_desc",
    "created_at","resolved_at","duration_hours","attachments","original_transaction_status","deleted_at",
}
AFTERSALES_DATE = {"created_at","resolved_at","deleted_at"}

REBATE_COLS = {
    "id","referrer_id","buyer_id","transaction_id","amount","rate","status","paid_at","notes","created_at",
}
REBATE_DATE = {"paid_at","created_at"}

TEMPLATE_COLS = {
    "id","name","default_cost","default_sale_price","category","warranty_days","is_active","created_at","updated_at",
}
TEMPLATE_DATE = {"created_at","updated_at"}

WARRANTY_EXT_COLS = {"id","transaction_id","old_end","new_end","extended_days","reason","created_at"}
WARRANTY_EXT_DATE = {"old_end","new_end","created_at"}

NOTIFICATION_COLS = {
    "id","type","ref_id","title","content","status","scheduled_at","sent_at","created_at",
}
NOTIFICATION_DATE = {"scheduled_at","sent_at","created_at"}

TAG_COLS = {"id","name","color","is_system","created_at"}
TAG_DATE = {"created_at"}

TAG_REL_COLS = {"id","customer_id","tag_id","created_at"}
TAG_REL_DATE = {"created_at"}

MAIL_COLS = {
    "id","to","customer_name","email_account","gpt_password","token_url","email_password",
    "subject","status","error","message_id","sent_at",
}
MAIL_DATE = {"sent_at"}


async def import_backup(db: AsyncSession, backup: dict) -> dict:
    """导入备份（覆盖式）。返回各表导入条数。"""
    data = backup.get("data") if isinstance(backup, dict) else None
    if not data or not isinstance(data, dict):
        raise ValueError("无效的备份文件格式：缺少 data 字段")

    await _clear_all(db)

    counts = {}

    def _bulk(model, rows, cols):
        objs = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            c = _clean_record(r, model, cols)
            if c:
                objs.append(model(**c))
        return objs

    # 导入顺序：先无外键依赖的表，再有依赖的
    if data.get("customers"):
        objs = _bulk(Customer, data["customers"], CUSTOMER_COLS)
        db.add_all(objs); counts["customers"] = len(objs)
    if data.get("product_templates"):
        objs = _bulk(ProductTemplate, data["product_templates"], TEMPLATE_COLS)
        db.add_all(objs); counts["product_templates"] = len(objs)
    if data.get("transactions"):
        objs = _bulk(Transaction, data["transactions"], TRANSACTION_COLS)
        db.add_all(objs); counts["transactions"] = len(objs)
    if data.get("customer_links"):
        objs = _bulk(CustomerLink, data["customer_links"], LINK_COLS)
        db.add_all(objs); counts["customer_links"] = len(objs)
    if data.get("after_sales"):
        objs = _bulk(AfterSales, data["after_sales"], AFTERSALES_COLS)
        db.add_all(objs); counts["after_sales"] = len(objs)
    if data.get("rebate_records"):
        objs = _bulk(RebateRecord, data["rebate_records"], REBATE_COLS)
        db.add_all(objs); counts["rebate_records"] = len(objs)
    if data.get("customer_tags"):
        objs = _bulk(CustomerTag, data["customer_tags"], TAG_COLS)
        db.add_all(objs); counts["customer_tags"] = len(objs)
    if data.get("customer_tag_relations"):
        objs = _bulk(CustomerTagRelation, data["customer_tag_relations"], TAG_REL_COLS)
        db.add_all(objs); counts["customer_tag_relations"] = len(objs)
    if data.get("warranty_extensions"):
        objs = _bulk(WarrantyExtension, data["warranty_extensions"], WARRANTY_EXT_COLS)
        db.add_all(objs); counts["warranty_extensions"] = len(objs)
    if data.get("notification_records"):
        objs = _bulk(NotificationRecord, data["notification_records"], NOTIFICATION_COLS)
        db.add_all(objs); counts["notification_records"] = len(objs)
    if data.get("mail_records"):
        # 邮件记录敏感字段加密
        objs = []
        for r in data["mail_records"]:
            if not isinstance(r, dict):
                continue
            c = _clean_record(r, MailRecord, MAIL_COLS)
            if c.get("gpt_password") and not is_encrypted(c["gpt_password"]):
                c["gpt_password"] = encrypt_field(c["gpt_password"])
            if c.get("email_password") and not is_encrypted(c["email_password"]):
                c["email_password"] = encrypt_field(c["email_password"])
            if c:
                objs.append(MailRecord(**c))
        db.add_all(objs); counts["mail_records"] = len(objs)
    if data.get("attachments"):
        objs = []
        for r in data["attachments"]:
            if not isinstance(r, dict):
                continue
            try:
                blob = base64.b64decode(r.get("base64", ""))
            except Exception:
                continue
            created = parse_date(r.get("created_at"))
            objs.append(Attachment(
                id=r.get("id"), name=r.get("name",""), type=r.get("type",""),
                size=r.get("size",0), blob=blob, created_at=created,
            ))
        db.add_all(objs); counts["attachments"] = len(objs)
    if data.get("settings"):
        # settings：单例。清洗（自动转日期）+ 加密 smtp_pass + 合并默认值
        for r in data["settings"]:
            if not isinstance(r, dict):
                continue
            # 清洗所有 Settings 列（含 created_at/updated_at 自动转 datetime）
            all_cols = set(DEFAULT_SETTINGS.keys()) | {"created_at", "updated_at"}
            c = _clean_record(r, SettingsModel, all_cols)
            if c.get("smtp_pass") and not is_encrypted(c["smtp_pass"]):
                c["smtp_pass"] = encrypt_field(c["smtp_pass"])
            c["id"] = 1
            # 默认值兜底
            merged = {**DEFAULT_SETTINGS, **{k: v for k, v in c.items() if v is not None}}
            merged["id"] = 1
            if c.get("smtp_pass"):
                merged["smtp_pass"] = c["smtp_pass"]
            db.add(SettingsModel(**merged))
            counts["settings"] = 1
            break

    await db.flush()
    return counts


async def export_backup(db: AsyncSession) -> dict:
    """导出全量数据为前端兼容格式（敏感字段解密为明文）。"""
    from .settings_service import get_settings_plain

    def _to_dict(obj, date_to_iso=True):
        d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        if date_to_iso:
            for k, v in list(d.items()):
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
        return d

    customers = [_to_dict(c) for c in (await db.execute(select(Customer))).scalars().all()]
    transactions = [_to_dict(c) for c in (await db.execute(select(Transaction))).scalars().all()]
    links = [_to_dict(c) for c in (await db.execute(select(CustomerLink))).scalars().all()]
    aftersales = [_to_dict(c) for c in (await db.execute(select(AfterSales))).scalars().all()]
    rebates = [_to_dict(c) for c in (await db.execute(select(RebateRecord))).scalars().all()]
    templates = [_to_dict(c) for c in (await db.execute(select(ProductTemplate))).scalars().all()]
    tags = [_to_dict(c) for c in (await db.execute(select(CustomerTag))).scalars().all()]
    tag_rels = [_to_dict(c) for c in (await db.execute(select(CustomerTagRelation))).scalars().all()]
    warranty_exts = [_to_dict(c) for c in (await db.execute(select(WarrantyExtension))).scalars().all()]
    notifications = [_to_dict(c) for c in (await db.execute(select(NotificationRecord))).scalars().all()]
    mail_records_raw = list((await db.execute(select(MailRecord))).scalars().all())
    mail_records = []
    for m in mail_records_raw:
        d = _to_dict(m)
        # 解密敏感字段为明文
        if d.get("gpt_password"):
            d["gpt_password"] = decrypt_field(d["gpt_password"])
        if d.get("email_password"):
            d["email_password"] = decrypt_field(d["email_password"])
        mail_records.append(d)
    attachments_raw = list((await db.execute(select(Attachment))).scalars().all())
    attachments = [{
        "id": a.id, "name": a.name, "type": a.type, "size": a.size,
        "base64": base64.b64encode(a.blob).decode("ascii"),
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in attachments_raw]

    settings_plain = await get_settings_plain(db)

    return {
        "version": "1.0",
        "export_time": now_iso(),
        "encrypted": False,
        "data": {
            "customers": customers,
            "transactions": transactions,
            "customer_links": links,
            "after_sales": aftersales,
            "rebate_records": rebates,
            "product_templates": templates,
            "settings": [settings_plain],
            "customer_tags": tags,
            "customer_tag_relations": tag_rels,
            "warranty_extensions": warranty_exts,
            "notification_records": notifications,
            "attachments": attachments,
            "mail_records": mail_records,
        },
    }


def now_iso() -> str:
    from ..utils.helpers import now_utc
    return now_utc().isoformat()
