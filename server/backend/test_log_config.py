"""P2-5 修复验证：结构化 JSON 日志 + request_id 链路追踪。

测试覆盖：
1. JsonFormatter 输出有效 JSON 且包含核心字段（ts/level/logger/msg）
2. 设置 request_id 后日志包含 request_id 字段
3. 未设置 request_id 时日志不包含 request_id 字段
4. 异常信息被正确序列化到 exception 字段
5. extra 字段被正确提取
6. configure_logging 替换 root logger 的 handler
7. new_request_id 生成唯一 ID
8. new_request_id 支持外部传入 ID
"""
import io
import json
import logging
import unittest

from app.log_config import (
    JsonFormatter,
    configure_logging,
    get_request_id,
    new_request_id,
    request_id_var,
)


def _make_record(
    msg: str = "test message",
    level: int = logging.INFO,
    name: str = "app.test",
    args: tuple = (),
    exc_info=None,
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


class JsonFormatterTests(unittest.TestCase):
    def setUp(self):
        # 清理 contextvar，避免测试间污染
        request_id_var.set(None)

    def tearDown(self):
        request_id_var.set(None)

    def test_log_record_is_valid_json(self):
        """日志输出为有效 JSON，包含核心字段。"""
        formatter = JsonFormatter()
        record = _make_record(msg="test message %s", args=("arg1",))
        output = formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "app.test")
        self.assertEqual(data["msg"], "test message arg1")
        self.assertIn("ts", data)

    def test_ts_format_is_iso8601(self):
        """时间戳为 ISO 8601 格式。"""
        formatter = JsonFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        # 格式应为 YYYY-MM-DDTHH:MM:SS.ffffffZ
        ts = data["ts"]
        self.assertTrue(ts.endswith("Z"))
        self.assertIn("T", ts)

    def test_request_id_included_when_set(self):
        """设置 request_id 后日志包含该字段。"""
        new_request_id("test-rid-12345")
        formatter = JsonFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["request_id"], "test-rid-12345")

    def test_request_id_absent_when_not_set(self):
        """未设置 request_id 时日志不包含该字段。"""
        request_id_var.set(None)
        formatter = JsonFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        self.assertNotIn("request_id", data)

    def test_exception_info_serialized(self):
        """异常堆栈被序列化到 exception 字段。"""
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = _make_record(exc_info=exc_info)
        output = formatter.format(record)
        data = json.loads(output)
        self.assertIn("exception", data)
        self.assertIn("ValueError", data["exception"])
        self.assertIn("test error", data["exception"])

    def test_extra_fields_extracted(self):
        """通过 extra 传入的字段被提取到 extra 对象。"""
        formatter = JsonFormatter()
        record = _make_record()
        record.user_id = 12345
        record.action = "login"
        output = formatter.format(record)
        data = json.loads(output)
        self.assertIn("extra", data)
        self.assertEqual(data["extra"]["user_id"], 12345)
        self.assertEqual(data["extra"]["action"], "login")

    def test_non_ascii_preserved(self):
        """中文字符不被转义（ensure_ascii=False）。"""
        formatter = JsonFormatter()
        record = _make_record(msg="用户登录成功")
        output = formatter.format(record)
        data = json.loads(output)
        self.assertEqual(data["msg"], "用户登录成功")
        # 原始输出中应直接包含中文，而非 \uXXXX 转义
        self.assertIn("用户登录成功", output)


class ConfigureLoggingTests(unittest.TestCase):
    def setUp(self):
        # 保存原始 root logger 状态
        self._original_handlers = logging.getLogger().handlers[:]
        self._original_level = logging.getLogger().level

    def tearDown(self):
        # 恢复原始 root logger
        root = logging.getLogger()
        root.handlers = self._original_handlers
        root.setLevel(self._original_level)
        request_id_var.set(None)

    def test_configure_logging_sets_json_handler(self):
        """configure_logging 将 root logger 的 handler 替换为 JsonFormatter。"""
        configure_logging(level=logging.DEBUG)
        root = logging.getLogger()
        self.assertEqual(root.level, logging.DEBUG)
        self.assertEqual(len(root.handlers), 1)
        handler = root.handlers[0]
        self.assertIsInstance(handler.formatter, JsonFormatter)

    def test_configure_logging_clears_existing_handlers(self):
        """configure_logging 清除已有 handler（避免重复输出）。"""
        root = logging.getLogger()
        # 添加一个 dummy handler
        root.addHandler(logging.StreamHandler())
        self.assertGreaterEqual(len(root.handlers), 1)

        configure_logging()
        self.assertEqual(len(root.handlers), 1)


class RequestIdTests(unittest.TestCase):
    def setUp(self):
        request_id_var.set(None)

    def tearDown(self):
        request_id_var.set(None)

    def test_new_request_id_generates_unique_id(self):
        """new_request_id() 生成唯一 ID。"""
        rid1 = new_request_id()
        rid2 = new_request_id()
        self.assertNotEqual(rid1, rid2)
        self.assertEqual(len(rid1), 12)

    def test_new_request_id_accepts_external_id(self):
        """new_request_id(rid) 支持外部传入 ID。"""
        rid = new_request_id("external-id-abc")
        self.assertEqual(rid, "external-id-abc")
        self.assertEqual(get_request_id(), "external-id-abc")

    def test_get_request_id_returns_none_by_default(self):
        """未设置时 get_request_id() 返回 None。"""
        self.assertIsNone(get_request_id())

    def test_get_request_id_returns_set_value(self):
        """设置后 get_request_id() 返回当前值。"""
        new_request_id("my-request-id")
        self.assertEqual(get_request_id(), "my-request-id")


if __name__ == "__main__":
    unittest.main()
