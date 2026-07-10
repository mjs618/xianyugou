"""Attachment upload, metadata, content, and deletion routes."""
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import AttachmentBatchRequest, AttachmentOut
from ..services import attachment_service


router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentOut)
async def upload_attachment(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content_type = file.content_type or ""
    if content_type not in attachment_service.ACCEPTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="仅支持 JPG/PNG/WebP/GIF 图片格式",
        )
    content = await file.read(attachment_service.MAX_ATTACHMENT_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="附件不能为空")
    if len(content) > attachment_service.MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=413, detail="附件大小不能超过 5MB")

    raw_name = (file.filename or "attachment").replace("\\", "/")
    name = Path(raw_name).name[:255] or "attachment"
    attachment = await attachment_service.create_attachment(
        db,
        name=name,
        content_type=content_type,
        content=content,
    )
    await db.commit()
    return attachment


@router.post("/batch", response_model=list[AttachmentOut])
async def batch_attachments(
    payload: AttachmentBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    return await attachment_service.get_attachments(db, payload.ids)


@router.get("/{attachment_id}/content")
async def attachment_content(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
):
    attachment = await attachment_service.get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    encoded_name = quote(attachment.name)
    return StreamingResponse(
        BytesIO(attachment.blob),
        media_type=attachment.type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}"
        },
    )


@router.delete("/{attachment_id}")
async def remove_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
):
    attachment = await attachment_service.get_attachment(db, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    await attachment_service.delete_attachment(db, attachment)
    await db.commit()
    return {"ok": True}
