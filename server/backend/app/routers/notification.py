"""通知路由

限流策略（project_memory 硬约束：100 req/min for read, stricter for write）：
- GET /api/notifications → 100/minute（读端点，已有 limit le=200）
- GET /api/notifications/unread-count → 100/minute（读端点）
- GET /api/notifications/pending-summary → 100/minute（读端点）
- POST /api/notifications/reminders/check → 30/minute（写端点，触发提醒检查）
- POST /api/notifications/{nid}/read → 30/minute（写端点）
- POST /api/notifications/read-all → 30/minute（写端点）
- POST /api/notifications/{nid}/dismiss → 30/minute（写端点）
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..security import limiter
from ..services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
@limiter.limit("100/minute")
async def list_notifications(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items = await notification_service.list_notifications(db, limit)
    await db.commit()
    return [_to_dict(n) for n in items]


@router.get("/unread-count")
@limiter.limit("100/minute")
async def unread_count(request: Request, db: AsyncSession = Depends(get_db)):
    cnt = await notification_service.get_unread_count(db)
    await db.commit()
    return {"count": cnt}


@router.get("/pending-summary")
@limiter.limit("100/minute")
async def pending_summary(request: Request, db: AsyncSession = Depends(get_db)):
    data = await notification_service.get_pending_summary(db)
    await db.commit()
    return data


@router.post("/reminders/check")
@limiter.limit("30/minute")
async def check_reminders(request: Request, db: AsyncSession = Depends(get_db)):
    """执行所有提醒检查，返回本次新生成的通知（供前端弹浏览器通知）。"""
    created = await notification_service.run_all_reminder_checks(db)
    await db.commit()
    return {"created": [_to_dict(n) for n in created]}


@router.post("/{nid}/read")
@limiter.limit("30/minute")
async def mark_read(request: Request, nid: int, db: AsyncSession = Depends(get_db)):
    try:
        await notification_service.mark_as_read(db, nid)
        await db.commit()
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/read-all")
@limiter.limit("30/minute")
async def mark_all_read(request: Request, db: AsyncSession = Depends(get_db)):
    await notification_service.mark_all_as_read(db)
    await db.commit()
    return {"ok": True}


@router.post("/{nid}/dismiss")
@limiter.limit("30/minute")
async def dismiss(request: Request, nid: int, db: AsyncSession = Depends(get_db)):
    try:
        await notification_service.dismiss(db, nid)
        await db.commit()
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


def _to_dict(n) -> dict:
    """序列化通知（日期转 ISO 字符串）"""
    return {
        "id": n.id, "type": n.type, "ref_id": n.ref_id, "title": n.title,
        "content": n.content, "status": n.status,
        "scheduled_at": n.scheduled_at.isoformat() if n.scheduled_at else None,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
