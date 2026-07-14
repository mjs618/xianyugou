"""认证相关 schema：token 状态查询与校验请求/响应。"""
from pydantic import BaseModel, Field


class TokenStatus(BaseModel):
    """GET /api/auth/token-status 响应：告知前端后端是否已配置 token。"""
    token_configured: bool = Field(..., description="后端是否已生成 API token")


class VerifyTokenRequest(BaseModel):
    """POST /api/auth/verify-token 请求体。"""
    token: str = Field(..., description="待校验的 token")


class VerifyTokenResponse(BaseModel):
    """POST /api/auth/verify-token 响应。"""
    valid: bool = Field(..., description="token 是否匹配")


class AuthError(BaseModel):
    """401 响应体。"""
    detail: str
