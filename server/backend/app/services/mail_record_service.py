"""邮件发送记录服务 - CRUD。敏感字段（gpt_password/email_password）后端已加密存储。"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MailRecord
from ..utils.helpers import now_utc


async def add_mail_record(db: AsyncSession, record: dict) -> int:
    """新增发送记录。敏感字段写入时由模型层加密（encrypt_field 在 router 处理）。"""
    m = MailRecord(**record)
    db.add(m)
    await db.flush()
    return m.id


async def list_mail_records(db: AsyncSession) -> list[MailRecord]:
    """查询所有记录（按发送时间倒序）。敏感字段读取时解密。"""
    stmt = select(MailRecord).order_by(MailRecord.sent_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def delete_mail_record(db: AsyncSession, rid: int) -> None:
    """删除单条记录。不存在时抛 ValueError（与 expense_service.delete_expense 一致）。"""
    existing = await db.get(MailRecord, rid)
    if existing is None:
        raise ValueError("邮件记录不存在")
    await db.delete(existing)


async def clear_mail_records(db: AsyncSession) -> None:
    await db.execute(delete(MailRecord))
