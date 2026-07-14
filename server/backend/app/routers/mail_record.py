"""邮件发送记录路由。敏感字段写入时加密、读取时解密。"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import MailRecordCreate
from ..services import mail_record_service
from ..utils.crypto import encrypt_field, decrypt_field

router = APIRouter(prefix="/api/mail-records", tags=["mail-records"])


def _to_dict(m, decrypt=True) -> dict:
    d = {
        "id": m.id, "to": m.to, "customer_name": m.customer_name,
        "email_account": m.email_account,
        "gpt_password": m.gpt_password, "token_url": m.token_url,
        "email_password": m.email_password, "subject": m.subject,
        "status": m.status, "error": m.error, "message_id": m.message_id,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
    }
    if decrypt:
        # 返回明文（前端展示用）
        d["gpt_password"] = decrypt_field(m.gpt_password) if m.gpt_password else ""
        d["email_password"] = decrypt_field(m.email_password) if m.email_password else ""
    return d


@router.get("")
async def list_mail_records(db: AsyncSession = Depends(get_db)):
    items = await mail_record_service.list_mail_records(db)
    await db.commit()
    return [_to_dict(m) for m in items]


@router.post("")
async def add_mail_record(payload: MailRecordCreate = Body(...), db: AsyncSession = Depends(get_db)):
    from ..utils.helpers import parse_date
    # 敏感字段加密存储；日期字段转 datetime
    record = payload.model_dump(exclude_unset=True)
    if record.get("gpt_password"):
        record["gpt_password"] = encrypt_field(record["gpt_password"])
    if record.get("email_password"):
        record["email_password"] = encrypt_field(record["email_password"])
    if record.get("sent_at"):
        record["sent_at"] = parse_date(record["sent_at"])
    rid = await mail_record_service.add_mail_record(db, record)
    await db.commit()
    return {"id": rid}


@router.delete("/{rid}")
async def delete_mail_record(rid: int, db: AsyncSession = Depends(get_db)):
    await mail_record_service.delete_mail_record(db, rid)
    await db.commit()
    return {"ok": True}


@router.delete("")
async def clear_mail_records(db: AsyncSession = Depends(get_db)):
    await mail_record_service.clear_mail_records(db)
    await db.commit()
    return {"ok": True}
