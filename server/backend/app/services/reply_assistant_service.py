"""回复助手配置、规则和风险分类服务。"""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ProductTemplate,
    ReplyAssistantSettings,
    ReplyRule,
)
from ..schemas.reply_assistant import (
    ReplyAssistantSettingsOut,
    ReplyAssistantSettingsUpdate,
    ReplyRuleCreate,
    ReplyRuleUpdate,
)
from ..utils.crypto import encrypt_field
from .audit_service import log_operation


class ReplyAssistantError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def get_settings(db: AsyncSession) -> ReplyAssistantSettings:
    settings = (
        await db.execute(
            select(ReplyAssistantSettings).where(ReplyAssistantSettings.id == 1)
        )
    ).scalar_one_or_none()
    if settings is None:
        settings = ReplyAssistantSettings(id=1)
        db.add(settings)
        await db.flush()
    return settings


async def get_public_settings(db: AsyncSession) -> ReplyAssistantSettingsOut:
    settings = await get_settings(db)
    return ReplyAssistantSettingsOut(
        id=settings.id,
        enabled=settings.enabled,
        ai_enabled=settings.ai_enabled,
        api_base_url=settings.api_base_url,
        api_key_configured=bool(settings.api_key),
        model=settings.model,
        system_prompt=settings.system_prompt,
    )


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    if not parsed.hostname:
        raise ReplyAssistantError("INVALID_API_BASE_URL", "API Base URL 格式无效")
    if parsed.scheme == "https":
        return normalized
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return normalized
    raise ReplyAssistantError(
        "INVALID_API_BASE_URL",
        "远程模型地址必须使用 HTTPS；HTTP 仅允许 localhost 或 127.0.0.1",
    )


async def update_settings(
    db: AsyncSession, payload: ReplyAssistantSettingsUpdate
) -> ReplyAssistantSettings:
    settings = await get_settings(db)
    patch = payload.model_dump(exclude_unset=True)
    clear_api_key = bool(patch.pop("clear_api_key", False))
    changed_keys: list[str] = []

    if clear_api_key:
        settings.api_key = ""
        changed_keys.append("api_key")

    for key, value in patch.items():
        if key == "api_key":
            if value:
                settings.api_key = encrypt_field(value)
                changed_keys.append(key)
            continue
        if isinstance(value, str):
            value = value.strip()
        if key == "api_base_url" and value is not None:
            value = _normalize_base_url(value)
        setattr(settings, key, value)
        changed_keys.append(key)

    await db.flush()
    if changed_keys:
        await log_operation(
            db,
            "reply_assistant",
            "settings_update",
            detail=f"修改字段: {', '.join(sorted(set(changed_keys)))}",
        )
    return settings


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        value = keyword.strip().casefold()
        if not value:
            continue
        if len(value) > 50:
            raise ReplyAssistantError(
                "INVALID_RULE_KEYWORD", "每个关键词最长 50 个字符"
            )
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    if not normalized:
        raise ReplyAssistantError("INVALID_RULE_KEYWORD", "至少需要一个有效关键词")
    return normalized


async def _require_product_template(
    db: AsyncSession, product_template_id: Optional[int]
) -> None:
    if product_template_id is None:
        return
    exists = (
        await db.execute(
            select(ProductTemplate.id).where(ProductTemplate.id == product_template_id)
        )
    ).scalar_one_or_none()
    if exists is None:
        raise ReplyAssistantError("PRODUCT_NOT_FOUND", "商品模板不存在", 404)


async def list_rules(db: AsyncSession) -> list[ReplyRule]:
    rows = (
        await db.execute(
            select(ReplyRule).order_by(
                ReplyRule.priority.desc(), ReplyRule.id.asc()
            )
        )
    ).scalars().all()
    return list(rows)


async def create_rule(db: AsyncSession, payload: ReplyRuleCreate) -> ReplyRule:
    await _require_product_template(db, payload.product_template_id)
    rule = ReplyRule(
        name=payload.name.strip(),
        enabled=payload.enabled,
        priority=payload.priority,
        keywords=_normalize_keywords(payload.keywords),
        reply_text=payload.reply_text.strip(),
        product_template_id=payload.product_template_id,
    )
    db.add(rule)
    await db.flush()
    await log_operation(
        db,
        "reply_assistant",
        "rule_create",
        target_id=rule.id,
        target_name=rule.name,
    )
    return rule


async def update_rule(
    db: AsyncSession, rule_id: int, payload: ReplyRuleUpdate
) -> ReplyRule:
    rule = await db.get(ReplyRule, rule_id)
    if rule is None:
        raise ReplyAssistantError("RULE_NOT_FOUND", "回复规则不存在", 404)
    patch: dict[str, Any] = payload.model_dump(exclude_unset=True)
    if "product_template_id" in patch:
        await _require_product_template(db, patch["product_template_id"])
    if "keywords" in patch:
        patch["keywords"] = _normalize_keywords(patch["keywords"])
    for key in ("name", "reply_text"):
        if key in patch:
            patch[key] = patch[key].strip()
    for key, value in patch.items():
        setattr(rule, key, value)
    await db.flush()
    await log_operation(
        db,
        "reply_assistant",
        "rule_update",
        target_id=rule.id,
        target_name=rule.name,
        detail=f"修改字段: {', '.join(sorted(patch))}",
    )
    return rule


async def delete_rule(db: AsyncSession, rule_id: int) -> None:
    rule = await db.get(ReplyRule, rule_id)
    if rule is None:
        raise ReplyAssistantError("RULE_NOT_FOUND", "回复规则不存在", 404)
    name = rule.name
    await db.execute(delete(ReplyRule).where(ReplyRule.id == rule_id))
    await log_operation(
        db,
        "reply_assistant",
        "rule_delete",
        target_id=rule_id,
        target_name=name,
    )


async def match_rule(
    db: AsyncSession,
    *,
    buyer_message: str,
    product_template_id: Optional[int],
) -> Optional[ReplyRule]:
    rules = (
        await db.execute(select(ReplyRule).where(ReplyRule.enabled.is_(True)))
    ).scalars().all()
    eligible = [
        rule
        for rule in rules
        if rule.product_template_id is None
        or rule.product_template_id == product_template_id
    ]
    eligible.sort(
        key=lambda rule: (
            0 if rule.product_template_id == product_template_id and product_template_id is not None else 1,
            -rule.priority,
            rule.id,
        )
    )
    normalized_message = buyer_message.casefold()
    return next(
        (
            rule
            for rule in eligible
            if any(keyword in normalized_message for keyword in rule.keywords)
        ),
        None,
    )


_RISK_CATEGORIES = {
    "议价": ("最低价", "改价", "便宜点", "优惠", "少点"),
    "私下付款": ("私下", "转账", "微信付款", "支付宝直接"),
    "退款售后": ("退款", "退货", "投诉", "举报", "平台介入"),
    "隐私认证": ("电话", "地址", "身份证", "验证码"),
    "账号异常": ("封禁", "处罚", "账号异常"),
}


def classify_risk(message: str) -> tuple[str, list[str]]:
    normalized = message.casefold()
    reasons = [
        category
        for category, keywords in _RISK_CATEGORIES.items()
        if any(keyword.casefold() in normalized for keyword in keywords)
    ]
    return ("manual_required", reasons) if reasons else ("normal", [])
