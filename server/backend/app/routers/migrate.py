"""JSON backup import and export routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import MigrateImportResponse
from ..services import migrate_service


router = APIRouter(prefix="/api/migrate", tags=["migrate"])


@router.post("/import", response_model=MigrateImportResponse)
async def import_backup(
    backup: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        counts = await migrate_service.import_backup(db, backup)
        await db.commit()
        return MigrateImportResponse(counts=counts, message="导入成功")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/export")
async def export_backup(db: AsyncSession = Depends(get_db)):
    data = await migrate_service.export_backup(db)
    await db.commit()
    return data
