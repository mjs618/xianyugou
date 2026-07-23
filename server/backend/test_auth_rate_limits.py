"""auth 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」+ 
verify-token 专有严格限流（防 token 暴力枚举）：

1. GET /api/auth/token-status 读端点 100/min（公开端点，缓解未认证探测）
2. POST /api/auth/verify-token 写端点 5/min（严格限流，防 token 暴力枚举）
"""
import unittest

from app.security.rate_limit import limiter


def _get_route_limit(module_path: str) -> str | None:
    """从 limiter._route_limits 中读取已注册的限流值。"""
    limits = limiter._route_limits.get(module_path)
    if not limits:
        return None
    return str(limits[0].limit)


def _assert_rate_limit(testcase, module_path: str, expected: str):
    """断言指定端点已挂载指定限流值。"""
    actual = _get_route_limit(module_path)
    testcase.assertIsNotNone(
        actual,
        f"{module_path} 未挂载 @limiter.limit 装饰器",
    )
    testcase.assertIn(
        expected,
        actual,
        f"{module_path} 限流值不匹配：期望含 {expected}，实际 {actual}",
    )
    testcase.assertIn(
        "minute",
        actual,
        f"{module_path} 限流单位应为 minute（项目约束：req/min/IP），实际 {actual}",
    )


class AuthRouteRateLimitDecorationTests(unittest.TestCase):
    """auth 路由所有端点必须挂载 @limiter.limit。"""

    def test_token_status_read_endpoint_limited_to_100_per_minute(self):
        """token-status 公开读端点 100/min（缓解未认证探测）。"""
        _assert_rate_limit(self, "app.routers.auth.token_status", "100")

    def test_verify_token_endpoint_limited_to_5_per_minute(self):
        """verify-token 严格限流 5/min（防 token 暴力枚举，已合规）。"""
        _assert_rate_limit(self, "app.routers.auth.verify", "5")


if __name__ == "__main__":
    unittest.main()
