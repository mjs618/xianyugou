"""认证路由：token 状态查询与校验。

这些端点本身不需要 X-API-Token 头（在 main.py 中间件中放行 /api/auth/*），
便于前端首次配置时探测与确认。
"""
from fastapi import APIRouter, HTTPException, Request

from ..schemas.auth import TokenStatus, VerifyTokenRequest, VerifyTokenResponse
from ..security import is_token_configured, limiter, verify_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/token-status", response_model=TokenStatus)
async def token_status():
    """返回后端 token 是否已配置。前端据此引导用户输入 token。"""
    return TokenStatus(token_configured=is_token_configured())


@router.post("/verify-token", response_model=VerifyTokenResponse)
@limiter.limit("5/minute")
async def verify(request: Request, payload: VerifyTokenRequest):
    """校验用户输入的 token 是否匹配后端持久化的 token。

    用于前端 Settings 页"测试并保存"按钮：成功则前端写入 sessionStorage。
    限流 5 次/分钟/IP，防止 token 暴力枚举。
    """
    valid = verify_token(payload.token)
    if not valid:
        raise HTTPException(401, "token 不匹配")
    return VerifyTokenResponse(valid=True)
