"""System settings routes.

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/settings → 100/minute（读端点，返回含解密 smtp_pass 的敏感数据）
- PUT /api/settings → 30/minute（写端点）
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import SettingsOut, SettingsUpdate
from ..security import limiter
from ..services import settings_service
from ..services.settings_service import SettingsError


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
@limiter.limit("100/minute")
async def get_settings(request: Request, db: AsyncSession = Depends(get_db)):
    data = await settings_service.get_settings_plain(db)
    await db.commit()
    return data


@router.put("", response_model=SettingsOut)
@limiter.limit("30/minute")
async def update_settings(
    request: Request,
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        await settings_service.update_settings(
            db,
            payload.model_dump(exclude_unset=True),
        )
        await db.commit()
        data = await settings_service.get_settings_plain(db)
        await db.commit()
        return data
    except SettingsError as exc:
        raise HTTPException(400, str(exc))
