"""通知路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    items = await notification_service.list_notifications(db, limit)
    await db.commit()
    return [_to_dict(n) for n in items]


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db)):
    cnt = await notification_service.get_unread_count(db)
    await db.commit()
    return {"count": cnt}


@router.get("/pending-summary")
async def pending_summary(db: AsyncSession = Depends(get_db)):
    data = await notification_service.get_pending_summary(db)
    await db.commit()
    return data


@router.post("/reminders/check")
async def check_reminders(db: AsyncSession = Depends(get_db)):
    """执行所有提醒检查，返回本次新生成的通知（供前端弹浏览器通知）。"""
    created = await notification_service.run_all_reminder_checks(db)
    await db.commit()
    return {"created": [_to_dict(n) for n in created]}


@router.post("/{nid}/read")
async def mark_read(nid: int, db: AsyncSession = Depends(get_db)):
    await notification_service.mark_as_read(db, nid)
    await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    await notification_service.mark_all_as_read(db)
    await db.commit()
    return {"ok": True}


@router.post("/{nid}/dismiss")
async def dismiss(nid: int, db: AsyncSession = Depends(get_db)):
    await notification_service.dismiss(db, nid)
    await db.commit()
    return {"ok": True}


def _to_dict(n) -> dict:
    """序列化通知（日期转 ISO 字符串）"""
    return {
        "id": n.id, "type": n.type, "ref_id": n.ref_id, "title": n.title,
        "content": n.content, "status": n.status,
        "scheduled_at": n.scheduled_at.isoformat() if n.scheduled_at else None,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
