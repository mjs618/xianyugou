"""pytest 配置：自动让现有测试绕过 API token 校验与速率限制。

设计：
- 现有测试主要测业务逻辑（财务、订单同步、客户等），与认证/限流无关。
  autouse fixture monkeypatch app.security.verify_token 永远返回 True，
  并禁用 slowapi limiter，避免每个测试 client 都需要手动注入 X-API-Token 头
  或担心触发 429。
- test_api_auth.py 测 token 中间件本身，通过 @pytest.mark.token_auth 标记跳过 autouse fixture。
- test_rate_limit.py 测限流本身，通过 @pytest.mark.rate_limit 标记跳过 limiter 禁用。
"""
import pytest

from app import security
from app.security import token as token_module


@pytest.fixture(autouse=True)
def bypass_api_token_for_business_tests(request):
    """默认绕过 token 校验。test_api_auth.py 用 @pytest.mark.token_auth 标记跳过此 fixture。"""
    marker = request.node.get_closest_marker("token_auth")
    if marker is not None:
        # 测 token 中间件本身：不绕过
        yield
        return
    # 业务测试：monkeypatch verify_token 永远返回 True
    original = security.verify_token
    token_module.verify_token = lambda t: True
    security.verify_token = lambda t: True
    try:
        yield
    finally:
        security.verify_token = original
        # token_module.verify_token 是原函数（未改），无需恢复


@pytest.fixture(autouse=True)
def disable_rate_limit_for_business_tests(request):
    """默认禁用 slowapi 限流。test_rate_limit.py 用 @pytest.mark.rate_limit 标记跳过此 fixture。"""
    marker = request.node.get_closest_marker("rate_limit")
    if marker is not None:
        # 测限流本身：不禁用
        yield
        return
    # 业务测试：禁用 limiter，避免触发 429
    from app.security.rate_limit import limiter
    original_enabled = limiter.enabled
    limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = original_enabled
