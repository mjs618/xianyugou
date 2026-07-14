"""数据库引擎与会话工厂（SQLAlchemy 2.0 异步）"""
from typing import AsyncGenerator

from sqlalchemy import event
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


# P2-1 修复：开启 SQLite WAL 模式提升读写并发能力
# - WAL（Write-Ahead Logging）：读不阻塞写、写不阻塞读
# - synchronous=NORMAL：WAL 模式下安全的折中，兼顾持久性与性能
# - busy_timeout=5000：写锁冲突时等待 5 秒再报 LOCKED，避免立即抛错
if settings.is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


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
