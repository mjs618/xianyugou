"""JSON backup import and export routes.

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/migrate/export → 100/minute（读端点，导出全库 JSON）
- POST /api/migrate/import → 3/minute（数据覆盖操作，严格限流，同 system/restore）
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import MigrateImportResponse
from ..security import limiter
from ..services import migrate_service


router = APIRouter(prefix="/api/migrate", tags=["migrate"])


@router.post("/import", response_model=MigrateImportResponse)
@limiter.limit("3/minute")
async def import_backup(
    request: Request,
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
@limiter.limit("100/minute")
async def export_backup(request: Request, db: AsyncSession = Depends(get_db)):
    data = await migrate_service.export_backup(db)
    await db.commit()
    return data
