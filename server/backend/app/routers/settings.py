"""System settings routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import SettingsOut, SettingsUpdate
from ..services import settings_service
from ..services.settings_service import SettingsError


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    data = await settings_service.get_settings_plain(db)
    await db.commit()
    return data


@router.put("", response_model=SettingsOut)
async def update_settings(
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
