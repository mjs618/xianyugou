"""Operation audit log routes.

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/operation-logs → 100/minute（读端点，已有 page_size le=200 限制）
- DELETE /api/operation-logs → 30/minute（写端点，清空操作）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import LogListResponse
from ..security import limiter
from ..services import audit_service


router = APIRouter(prefix="/api/operation-logs", tags=["audit"])


@router.get("", response_model=LogListResponse)
@limiter.limit("100/minute")
async def list_logs(
    request: Request,
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
@limiter.limit("30/minute")
async def clear_logs(request: Request, db: AsyncSession = Depends(get_db)):
    await audit_service.clear_logs(db)
    await db.commit()
    return {"message": "日志已清空"}
