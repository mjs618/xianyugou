"""附件模型 - 存储图片二进制（与前端 IndexedDB 的 Blob 对齐）"""
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    # 二进制内容（前端是 Blob，后端用 BLOB/字节存储）
    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
