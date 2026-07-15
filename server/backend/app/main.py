"""FastAPI 应用入口

启动：cd server/backend && uvicorn app.main:app --reload --port 8000
文档：http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings as app_settings
from .database import init_db
from .log_config import configure_logging, new_request_id, get_request_id
from .schemas import HealthResponse
from . import security
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
    auth,
    metrics,
    system,
)

# P2-5 修复：结构化 JSON 日志（替代原 basicConfig）
# 便于 ELK/Loki 等日志聚合系统采集，支持 request_id 链路追踪
configure_logging(level=logging.INFO)

# 不需要 X-API-Token 的路径白名单：
# - /api/health：探活，必须放行
# - /api/auth/*：token 状态查询与校验，否则前端首次配置无法引导
_PUBLIC_PATH_PREFIXES = ("/api/health", "/api/auth/")
_PUBLIC_PATHS = {"/api/health"}


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
    # P1-2：启动定时备份调度器（默认每小时检查，24h 触发一次备份）
    from .maintenance.backup_scheduler import scheduler as backup_scheduler
    backup_scheduler.start()
    try:
        yield
    finally:
        await sync_scheduler.stop()
        await backup_scheduler.stop()


app = FastAPI(
    title=app_settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# P1-1 速率限制：注册 slowapi limiter + 异常处理 + 中间件
app.state.limiter = security.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def verify_api_token_middleware(request: Request, call_next):
    """P0-1 修复：校验所有 /api/* 请求的 X-API-Token 头。

    放行规则：
    - 非 /api/ 路径（如 /docs、/openapi.json）：放行
    - /api/health：探活，放行
    - /api/auth/*：token 状态查询与校验，放行（首次配置时必需）
    - 其余 /api/* 请求：必须携带有效 X-API-Token 头，否则 401
    """
    path = request.url.path
    # OPTIONS 预检请求直接放行：浏览器 CORS 流程在实际请求前先发 OPTIONS，
    # 此时无法携带 X-API-Token（浏览器尚未读取 sessionStorage 注入头），
    # 若拦截会返回 401，前端表现为"无法连接后端服务"。
    if request.method == "OPTIONS":
        return await call_next(request)
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PATH_PREFIXES[1]):
        return await call_next(request)
    token = request.headers.get("X-API-Token", "")
    if not security.verify_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "未授权：缺少或无效的 X-API-Token"},
        )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """P2-5 修复：注入 request_id 并在响应头返回，串联请求链路日志。

    request_id 来源（按优先级）：
    1. 上游传入的 X-Request-ID 头（如经 nginx 转发）
    2. 自动生成的 12 位十六进制 ID

    设置到 contextvar 后，同一请求内所有日志（JsonFormatter）都会包含此 ID。
    响应头 X-Request-ID 返回给客户端，便于前端/运维关联请求。

    注：此中间件定义在 verify_api_token 之后（LIFO 模型中最外层），
    因此对所有请求（包括 401 未授权）都注入 request_id，便于追踪被拒请求。
    """
    incoming_rid = request.headers.get("X-Request-ID")
    rid = new_request_id(incoming_rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# CORS 必须在认证中间件之后注册，使其位于外层并为 401 响应补齐跨域头。
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
app.include_router(auth.router)
app.include_router(metrics.router)
app.include_router(system.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_settings.host,
        port=app_settings.port,
        reload=True,
    )
