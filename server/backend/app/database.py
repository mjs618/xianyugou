"""数据库引擎与会话工厂（SQLAlchemy 2.0 异步）"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
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
    """验证数据库处于运维人员管理的 Alembic head 版本。"""
    from .config import DEFAULT_DB_PATH
    from .maintenance.database_schema import require_current_schema

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    await require_current_schema(engine)
