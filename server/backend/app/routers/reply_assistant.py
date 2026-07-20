"""回复助手配置、规则与候选生成接口。

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/reply-assistant/settings → 100/minute（读端点）
- PUT /api/reply-assistant/settings → 30/minute（写端点）
- GET /api/reply-assistant/rules → 100/minute（读端点）
- POST /api/reply-assistant/rules → 30/minute（写端点）
- PATCH /api/reply-assistant/rules/{rule_id} → 30/minute（写端点）
- DELETE /api/reply-assistant/rules/{rule_id} → 30/minute（写端点）
- POST /api/reply-assistant/suggestions → 30/minute（写端点，触发 LLM 调用）
- POST /api/reply-assistant/risk-check → 30/minute（写端点）
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.reply_assistant import (
    ReplyAssistantSettingsOut,
    ReplyAssistantSettingsUpdate,
    ReplyRuleCreate,
    ReplyRuleOut,
    ReplyRuleUpdate,
    ReplySuggestionOut,
    ReplySuggestionRequest,
    RiskCheckRequest,
    RiskCheckResponse,
)
from ..security import limiter
from ..services import reply_assistant_service
from ..services.llm_client import LlmClientError


router = APIRouter(prefix="/api/reply-assistant", tags=["reply-assistant"])
ReplyAssistantError = reply_assistant_service.ReplyAssistantError


def _http_error(exc: ReplyAssistantError | LlmClientError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )

@router.get("/settings", response_model=ReplyAssistantSettingsOut)
@limiter.limit("100/minute")
async def get_settings(request: Request, db: AsyncSession = Depends(get_db)):
    return await reply_assistant_service.get_public_settings(db)


@router.put("/settings", response_model=ReplyAssistantSettingsOut)
@limiter.limit("30/minute")
async def update_settings(
    request: Request,
    payload: ReplyAssistantSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        await reply_assistant_service.update_settings(db, payload)
        await db.commit()
        return await reply_assistant_service.get_public_settings(db)
    except ReplyAssistantError as exc:
        raise _http_error(exc) from exc


@router.get("/rules", response_model=list[ReplyRuleOut])
@limiter.limit("100/minute")
async def list_rules(request: Request, db: AsyncSession = Depends(get_db)):
    return await reply_assistant_service.list_rules(db)


@router.post("/rules", response_model=ReplyRuleOut)
@limiter.limit("30/minute")
async def create_rule(
    request: Request,
    payload: ReplyRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        rule = await reply_assistant_service.create_rule(db, payload)
        await db.commit()
        await db.refresh(rule)
        return rule
    except ReplyAssistantError as exc:
        raise _http_error(exc) from exc


@router.patch("/rules/{rule_id}", response_model=ReplyRuleOut)
@limiter.limit("30/minute")
async def update_rule(
    request: Request,
    rule_id: int,
    payload: ReplyRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        rule = await reply_assistant_service.update_rule(db, rule_id, payload)
        await db.commit()
        await db.refresh(rule)
        return rule
    except ReplyAssistantError as exc:
        raise _http_error(exc) from exc


@router.delete("/rules/{rule_id}")
@limiter.limit("30/minute")
async def delete_rule(
    request: Request, rule_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        await reply_assistant_service.delete_rule(db, rule_id)
        await db.commit()
        return {"message": "已删除"}
    except ReplyAssistantError as exc:
        raise _http_error(exc) from exc


@router.post("/suggestions", response_model=ReplySuggestionOut)
@limiter.limit("30/minute")
async def generate_suggestion(
    request: Request,
    payload: ReplySuggestionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await reply_assistant_service.generate_suggestion(db, payload)
        await db.commit()
        return result
    except (ReplyAssistantError, LlmClientError) as exc:
        raise _http_error(exc) from exc


@router.post("/risk-check", response_model=RiskCheckResponse)
@limiter.limit("30/minute")
async def check_risk(request: Request, payload: RiskCheckRequest):
    risk_level, risk_reasons = reply_assistant_service.check_reply_risk(payload.text)
    return RiskCheckResponse(
        risk_level=risk_level, risk_reasons=risk_reasons
    )
