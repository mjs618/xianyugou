"""Attachment persistence operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Attachment


MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024
ACCEPTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def create_attachment(
    db: AsyncSession,
    *,
    name: str,
    content_type: str,
    content: bytes,
) -> Attachment:
    attachment = Attachment(
        name=name,
        type=content_type,
        size=len(content),
        blob=content,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def get_attachment(
    db: AsyncSession,
    attachment_id: int,
) -> Attachment | None:
    return await db.get(Attachment, attachment_id)


async def get_attachments(
    db: AsyncSession,
    ids: list[int],
) -> list[Attachment]:
    if not ids:
        return []
    items = list(
        (
            await db.execute(select(Attachment).where(Attachment.id.in_(ids)))
        ).scalars().all()
    )
    by_id = {item.id: item for item in items}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


async def delete_attachment(
    db: AsyncSession,
    attachment: Attachment,
) -> None:
    await db.delete(attachment)
    await db.flush()
