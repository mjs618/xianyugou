"""FastAPI 应用入口

启动：cd server/backend && uvicorn app.main:app --reload --port 8000
文档：http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings as app_settings
from .database import init_db
from .schemas import HealthResponse
from .utils.crypto import _load_or_create_key
from .routers import (
    customers, transactions, aftersales, rebates,
    settings,
    product_templates,
    finance,
    expenses,
    audit,
    migrate,
    xianyu,
    warranty,
    referral,
    notification,
    customer_tag,
    trash,
    mail_record,
    attachments,
)

# 配置 app.* 日志输出到控制台（uvicorn 默认只配置自己的 logger）
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 迁移加密存量敏感字段 + 启动自动同步调度器。"""
    _load_or_create_key()
    await init_db()
    # 存量明文敏感字段自动加密
    from .database import AsyncSessionLocal
    from .services.settings_service import migrate_encrypt_settings
    async with AsyncSessionLocal() as db:
        await migrate_encrypt_settings(db)
        await db.commit()
    # P3：启动安全自动同步调度器（默认 60 秒 tick）
    from .services.sync_scheduler import scheduler as sync_scheduler
    sync_scheduler.start()
    try:
        yield
    finally:
        await sync_scheduler.stop()


app = FastAPI(
    title=app_settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: configured by CORS_ORIGINS, comma-separated.
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health():
    from .services.sync_scheduler import scheduler
    return HealthResponse(
        time=datetime.now(timezone.utc).isoformat(),
        scheduler_running=scheduler.running,
    )


# 注册路由
app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(aftersales.router)
app.include_router(rebates.router)
app.include_router(settings.router)
app.include_router(product_templates.router)
app.include_router(finance.router)
app.include_router(expenses.router)
app.include_router(audit.router)
app.include_router(migrate.router)
app.include_router(xianyu.router)
app.include_router(warranty.router)
app.include_router(referral.router)
app.include_router(notification.router)
app.include_router(customer_tag.router)
app.include_router(trash.router)
app.include_router(mail_record.router)
app.include_router(attachments.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_settings.host,
        port=app_settings.port,
        reload=True,
    )
