"""API 安全模块：预共享 Token 认证 + 速率限制。

对应设计文档 P0-1 修复：所有 /api/* 端点（除 /api/health 与 /api/auth/*）
必须携带有效 X-API-Token 头，否则返回 401。

对应设计文档 P1-1 修复：slowapi 限流器，防 API 暴力枚举/爬取。

Token 在后端首次启动时随机生成并持久化到 data/api.token，前端在 Settings
页面配置后存入 sessionStorage，每次请求自动注入 X-API-Token 头。
"""
from .rate_limit import limiter
from .token import (
    get_api_token,
    is_token_configured,
    verify_token,
)

__all__ = [
    "get_api_token",
    "is_token_configured",
    "verify_token",
    "limiter",
]

