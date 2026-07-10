"""Operation audit log routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import LogListResponse
from ..services import audit_service


router = APIRouter(prefix="/api/operation-logs", tags=["audit"])


@router.get("", response_model=LogListResponse)
async def list_logs(
    module: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_service.list_logs(
        db,
        module=module,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    await db.commit()
    return {"items": items, "total": total}


@router.delete("")
async def clear_logs(db: AsyncSession = Depends(get_db)):
    await audit_service.clear_logs(db)
    await db.commit()
    return {"message": "日志已清空"}
