"""system 路由限流装饰器测试。

验证 project_memory 硬约束「API rate limiting must be implemented
(100 req/min for read endpoints, stricter for write endpoints)」+ 
「API 路由限流 3/分钟」（restore 专有约束）：

1. GET /api/system/backups 读端点 100/min
2. POST /api/system/restore 写端点 3/min（project_memory 硬约束，已合规）
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


class SystemRouteRateLimitDecorationTests(unittest.TestCase):
    """system 路由所有端点必须挂载 @limiter.limit。"""

    def test_system_backups_read_endpoint_limited_to_100_per_minute(self):
        _assert_rate_limit(self, "app.routers.system.list_backups", "100")

    def test_system_restore_endpoint_limited_to_3_per_minute(self):
        """restore 是不可逆操作，project_memory 硬约束要求 3/分钟（已合规）。"""
        _assert_rate_limit(self, "app.routers.system.restore", "3")


if __name__ == "__main__":
    unittest.main()
