"""回复助手配置、规则和风险分类服务。"""
from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ProductTemplate,
    ReplyAssistantSettings,
    ReplyRule,
    XianyuAccount,
)
from ..schemas.reply_assistant import (
    ReplyAssistantSettingsOut,
    ReplyAssistantSettingsUpdate,
    ReplyRuleCreate,
    ReplyRuleUpdate,
    ReplySuggestionOut,
    ReplySuggestionRequest,
)
from ..utils.crypto import decrypt_field, encrypt_field
from .audit_service import log_operation
from .llm_client import LlmConfig, request_chat_completion


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


def check_reply_risk(text: str) -> tuple[str, list[str]]:
    """对用户编辑后的最终候选文本执行本地关键词风险分类。

    不访问数据库、AI、闲鱼网络或外部 URL；不记录请求正文。
    """
    return classify_risk(text.strip())


def _merge_risk(
    buyer_reasons: list[str], reply_reasons: list[str]
) -> tuple[str, list[str]]:
    """合并买家消息和候选回复触发的风险原因并去重，保持稳定顺序。"""
    seen: set[str] = set()
    merged: list[str] = []
    for reason in [*buyer_reasons, *reply_reasons]:
        if reason not in seen:
            seen.add(reason)
            merged.append(reason)
    return ("manual_required" if merged else "normal", merged)


async def _get_account(db: AsyncSession, account_id: int) -> XianyuAccount:
    account = await db.get(XianyuAccount, account_id)
    if account is None or account.deleted_at is not None:
        raise ReplyAssistantError("ACCOUNT_NOT_FOUND", "闲鱼账号不存在", 404)
    return account


async def _get_product(
    db: AsyncSession, product_template_id: Optional[int]
) -> Optional[ProductTemplate]:
    if product_template_id is None:
        return None
    product = await db.get(ProductTemplate, product_template_id)
    if product is None:
        raise ReplyAssistantError("PRODUCT_NOT_FOUND", "商品模板不存在", 404)
    return product


def _build_messages(
    settings: ReplyAssistantSettings,
    product: Optional[ProductTemplate],
    payload: ReplySuggestionRequest,
) -> list[dict[str, str]]:
    system_parts = [
        "你是闲鱼卖家的回复辅助工具，只生成供人工核对和复制的候选回复。"
        "不得编造价格、库存、物流时间、退款承诺或平台政策。",
    ]
    if settings.system_prompt.strip():
        system_parts.append(settings.system_prompt.strip())
    if product is not None:
        price = (
            str(product.default_sale_price)
            if product.default_sale_price is not None
            else "未设置"
        )
        system_parts.append(f"商品名称：{product.name}\n默认售价：{price}")

    system_message = {"role": "system", "content": "\n\n".join(system_parts)}
    context = [
        {
            "role": "user" if item.role == "user" else "assistant",
            "content": item.content.strip(),
        }
        for item in payload.context_messages
        if item.content.strip()
    ]
    latest = {"role": "user", "content": payload.buyer_message.strip()}

    def total_chars(items: list[dict[str, str]]) -> int:
        return sum(len(item["content"]) for item in items)

    messages = [system_message, *context, latest]
    while context and total_chars(messages) > 12000:
        context.pop(0)
        messages = [system_message, *context, latest]
    return messages


async def _audit_suggestion(
    db: AsyncSession,
    *,
    payload: ReplySuggestionRequest,
    source: str,
    risk_level: str,
    matched_rule_id: Optional[int],
) -> None:
    detail = json.dumps(
        {
            "account_id": payload.account_id,
            "product_template_id": payload.product_template_id,
            "source": source,
            "risk_level": risk_level,
            "matched_rule_id": matched_rule_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    await log_operation(
        db,
        "reply_assistant",
        "suggestion_generate",
        target_id=payload.account_id,
        detail=detail,
    )


async def generate_suggestion(
    db: AsyncSession, payload: ReplySuggestionRequest
) -> ReplySuggestionOut:
    settings = await get_settings(db)
    if not settings.enabled:
        raise ReplyAssistantError("ASSISTANT_DISABLED", "回复助手尚未启用", 409)

    await _get_account(db, payload.account_id)
    product = await _get_product(db, payload.product_template_id)
    buyer_message = payload.buyer_message.strip()
    if not buyer_message:
        raise ReplyAssistantError("EMPTY_BUYER_MESSAGE", "买家消息不能为空")

    risk_level, risk_reasons = classify_risk(buyer_message)
    rule = await match_rule(
        db,
        buyer_message=buyer_message,
        product_template_id=payload.product_template_id,
    )
    if rule is not None:
        reply_risk_level, reply_risk_reasons = classify_risk(rule.reply_text)
        risk_level, risk_reasons = _merge_risk(risk_reasons, reply_risk_reasons)
        result = ReplySuggestionOut(
            reply=rule.reply_text,
            source="rule",
            matched_rule_id=rule.id,
            risk_level=risk_level,
            risk_reasons=risk_reasons,
        )
        await _audit_suggestion(
            db,
            payload=payload,
            source=result.source,
            risk_level=result.risk_level,
            matched_rule_id=result.matched_rule_id,
        )
        return result

    if not settings.ai_enabled:
        raise ReplyAssistantError(
            "NO_REPLY_AVAILABLE", "没有匹配的固定规则，且 AI 回复未启用", 422
        )
    if not settings.api_base_url or not settings.api_key or not settings.model:
        raise ReplyAssistantError(
            "AI_NOT_CONFIGURED", "AI 回复配置不完整，请检查地址、密钥和模型", 409
        )

    reply = await request_chat_completion(
        LlmConfig(
            api_base_url=settings.api_base_url,
            api_key=decrypt_field(settings.api_key),
            model=settings.model,
        ),
        _build_messages(settings, product, payload),
    )
    reply = reply.strip()[:1000]
    reply_risk_level, reply_risk_reasons = classify_risk(reply)
    risk_level, risk_reasons = _merge_risk(risk_reasons, reply_risk_reasons)
    result = ReplySuggestionOut(
        reply=reply,
        source="ai",
        risk_level=risk_level,
        risk_reasons=risk_reasons,
    )
    await _audit_suggestion(
        db,
        payload=payload,
        source=result.source,
        risk_level=result.risk_level,
        matched_rule_id=None,
    )
    return result
