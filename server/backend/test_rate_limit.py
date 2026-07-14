"""P1-1 速率限制测试：验证 slowapi 装饰器在超限后返回 429。

覆盖：
1. /api/auth/verify-token 在限额内（5 次）返回正常响应
2. 第 6 次调用触发 429 Too Many Requests
"""
import unittest

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security import token as token_module
from app.security.rate_limit import limiter


@pytest.mark.rate_limit
class RateLimitTests(unittest.IsolatedAsyncioTestCase):
    """测 slowapi 限流本身：用 @pytest.mark.rate_limit 标记跳过 conftest 的 limiter 禁用。

    注意：这些测试用 @pytest.mark.rate_limit 但不用 @pytest.mark.token_auth，
    因为 /api/auth/* 已被中间件放行，无需 token。但 token bypass fixture 仍生效，
    不影响本测试（verify-token 自身不经过 verify_token 中间件检查）。
    """

    async def asyncSetUp(self):
        # 用固定的测试 token，让 verify-token 能返回 200（valid=True）
        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "rate-limit-test-token-xyz"
        # 重置 limiter 存储状态，避免前序测试残留计数
        try:
            limiter._storage.reset()
        except Exception:
            pass

    async def asyncTearDown(self):
        token_module.get_api_token = self._original_get
        try:
            limiter._storage.reset()
        except Exception:
            pass

    async def test_verify_token_allows_5_requests_per_minute(self):
        """/api/auth/verify-token 限流 5 次/分钟：前 5 次应返回 200 或 401（token 不匹配），
        关键是「不是 429」。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for i in range(5):
                response = await client.post(
                    "/api/auth/verify-token",
                    json={"token": "rate-limit-test-token-xyz"},
                )
                # 前 5 次不应被限流（200 表示 token 正确）
                self.assertNotEqual(
                    response.status_code,
                    429,
                    f"第 {i + 1} 次调用不应返回 429",
                )

    async def test_verify_token_returns_429_on_6th_request(self):
        """第 6 次调用应触发 429 Too Many Requests。"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 前 5 次正常调用
            for i in range(5):
                await client.post(
                    "/api/auth/verify-token",
                    json={"token": "rate-limit-test-token-xyz"},
                )
            # 第 6 次应被限流
            response = await client.post(
                "/api/auth/verify-token",
                json={"token": "rate-limit-test-token-xyz"},
            )
            self.assertEqual(response.status_code, 429)


if __name__ == "__main__":
    unittest.main()
