"""FastAPI 应用入口

启动：cd server/backend && uvicorn app.main:app --reload --port 8000
文档：http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .schemas import HealthResponse
from .utils.crypto import _load_or_create_key
from .routers import (
    customers, transactions, aftersales, rebates,
    settings as settings_router_module,
    xianyu,
    warranty,
    referral,
    notification,
    customer_tag,
    trash,
    mail_record,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 迁移加密存量敏感字段。"""
    _load_or_create_key()
    await init_db()
    # 存量明文敏感字段自动加密
    from .database import AsyncSessionLocal
    from .services.settings_service import migrate_encrypt_settings
    async with AsyncSessionLocal() as db:
        await migrate_encrypt_settings(db)
        await db.commit()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: configured by CORS_ORIGINS, comma-separated.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health():
    return HealthResponse(time=datetime.now(timezone.utc).isoformat())


# 注册路由
app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(aftersales.router)
app.include_router(rebates.router)
app.include_router(settings_router_module.settings_router)
app.include_router(settings_router_module.templates_router)
app.include_router(settings_router_module.finance_router)
app.include_router(settings_router_module.audit_router)
app.include_router(settings_router_module.migrate_router)
app.include_router(xianyu.router)
app.include_router(warranty.router)
app.include_router(referral.router)
app.include_router(notification.router)
app.include_router(customer_tag.router)
app.include_router(trash.router)
app.include_router(mail_record.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
