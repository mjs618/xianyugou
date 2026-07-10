"""数据库引擎与会话工厂（SQLAlchemy 2.0 异步）"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# 异步引擎。SQLite 需开启 check_same_thread=False 以支持多请求
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if settings.is_sqlite else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每个请求获取一个独立会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """建表（首次启动 / 模型变更后调用）。"""
    # 确保数据目录存在（SQLite）
    from .config import DEFAULT_DB_PATH
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 导入所有模型，确保它们被注册到 Base.metadata
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            await _ensure_sqlite_columns(conn)


async def _ensure_sqlite_columns(conn) -> None:
    """补齐轻量字段迁移；create_all 不会给既有 SQLite 表新增列。"""
    product_columns = {
        row[1]
        for row in (await conn.execute(text("PRAGMA table_info(product_templates)"))).fetchall()
    }
    if "source_xianyu_account_id" not in product_columns:
        await conn.execute(text("ALTER TABLE product_templates ADD COLUMN source_xianyu_account_id INTEGER"))
    if "source_xianyu_item_id" not in product_columns:
        await conn.execute(text("ALTER TABLE product_templates ADD COLUMN source_xianyu_item_id VARCHAR(64)"))
    if "image_url" not in product_columns:
        await conn.execute(text("ALTER TABLE product_templates ADD COLUMN image_url TEXT"))

    transaction_columns = {
        row[1]
        for row in (await conn.execute(text("PRAGMA table_info(transactions)"))).fetchall()
    }
    if "shipped_at" not in transaction_columns:
        await conn.execute(text("ALTER TABLE transactions ADD COLUMN shipped_at DATETIME"))

    await conn.execute(text("""
        UPDATE product_templates
        SET image_url = (
            SELECT xi.image_url
            FROM xianyu_items xi
            WHERE xi.account_id = product_templates.source_xianyu_account_id
              AND xi.item_id = product_templates.source_xianyu_item_id
            LIMIT 1
        )
        WHERE image_url IS NULL
          AND source_xianyu_account_id IS NOT NULL
          AND source_xianyu_item_id IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM xianyu_items xi
            WHERE xi.account_id = product_templates.source_xianyu_account_id
              AND xi.item_id = product_templates.source_xianyu_item_id
              AND xi.image_url IS NOT NULL
          )
    """))
