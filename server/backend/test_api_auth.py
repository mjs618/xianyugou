"""P0-1 修复验证：API Token 认证中间件。

覆盖：
1. /api/health 不需要 token（探活放行）
2. /api/auth/token-status 不需要 token（首次配置引导）
3. /api/auth/verify-token 不需要 token（校验入口本身放行）
4. 业务端点无 token 返回 401
5. 业务端点错误 token 返回 401
6. 业务端点正确 token 返回 200
"""
import unittest

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings as app_settings
from app.main import app
from app.security import token as token_module


@pytest.mark.token_auth
class ApiAuthMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    """测中间件本身：用 @pytest.mark.token_auth 标记跳过 conftest 的 autouse 绕过。"""

    async def asyncSetUp(self):
        # 用固定的测试 token，避免影响真实 data/api.token
        self._original_get = token_module.get_api_token
        token_module.get_api_token = lambda: "test-token-fixed-xyz"
        self.test_token = "test-token-fixed-xyz"

    async def asyncTearDown(self):
        token_module.get_api_token = self._original_get

    async def test_health_endpoint_does_not_require_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")
        self.assertEqual(response.status_code, 200)

    async def test_auth_token_status_does_not_require_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/auth/token-status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("token_configured", response.json())

    async def test_auth_verify_token_endpoint_does_not_require_token_for_getting_status(self):
        # verify-token 本身是 POST，需要不带 token 也能访问
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/auth/verify-token", json={"token": "test-token-fixed-xyz"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    async def test_business_endpoint_without_token_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/transactions")
        self.assertEqual(response.status_code, 401)
        self.assertIn("X-API-Token", response.json()["detail"])

    async def test_business_endpoint_401_includes_cors_headers(self):
        origin = app_settings.cors_origin_list[0]
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/transactions", headers={"Origin": origin}
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)

    async def test_business_endpoint_with_wrong_token_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/transactions", headers={"X-API-Token": "wrong"}
            )
        self.assertEqual(response.status_code, 401)

    async def test_business_endpoint_with_correct_token_returns_not_401(self):
        """正确 token 通过中间件后到达业务层。业务层可能因测试无 DB 返回 500/抛异常，
        关键判定是「不是 401」（即 token 已通过）。"""
        from sqlalchemy.exc import OperationalError
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            try:
                response = await client.get(
                    "/api/transactions", headers={"X-API-Token": self.test_token}
                )
                # 未抛异常：断言不是 401
                self.assertNotEqual(response.status_code, 401)
            except OperationalError:
                # 抛 OperationalError 说明已通过中间件到达 DB 层（测试未建表），
                # 这本身证明 token 通过
                pass


if __name__ == "__main__":
    unittest.main()
