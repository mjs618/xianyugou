"""P1-1 速率限制配置。

使用 slowapi 实现 API 限流，防暴力枚举与爬取：
- 认证类端点（/api/auth/verify-token）：5 req/min/IP（防 token 暴力枚举）
- 写操作端点（POST/PATCH/DELETE）：30 req/min/IP
- 全局默认：100 req/min/IP（通过 SlowAPIMiddleware 或按需装饰器）

使用方式：
    from app.security.rate_limit import limiter

    @router.post("")
    @limiter.limit("30/minute")
    async def create_endpoint(request: Request, ...):
        ...

注意：slowapi 装饰器要求端点函数有 `request: Request` 形参。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 按客户端 IP 限流。X-Forwarded-For 由反向代理（nginx）设置；
# get_remote_address 自动处理，生产环境需确保代理正确设置该头。
limiter = Limiter(key_func=get_remote_address)
