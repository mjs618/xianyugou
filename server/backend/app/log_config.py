"""结构化日志配置：JSON 格式 + request_id 链路追踪。

对应设计文档 P2-5：日志从纯文本改为 JSON，便于日志聚合系统（ELK/Loki）采集。
request_id 通过 contextvar 在同一请求内串联所有日志，便于追踪请求链路。

输出格式示例：
  {"ts": "2026-07-13T10:30:00.123456Z", "level": "INFO", "logger": "app.main",
   "msg": "请求处理完成", "request_id": "a1b2c3d4e5f6"}
"""
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

# 请求级 contextvar：同一请求内所有日志共享同一 request_id
# 在中间件中设置后，下游所有 logger 调用都能读取到同一个 request_id
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """JSON 日志格式化器。

    输出字段：
    - ts: ISO 8601 时间戳（含微秒）
    - level: 日志级别（INFO/WARNING/ERROR 等）
    - logger: logger 名称（如 app.services.xxx）
    - msg: 日志消息（已格式化）
    - request_id: 请求 ID（如果通过中间件设置）
    - exception: 异常堆栈（如果记录了 exc_info）
    - extra: 额外字段（通过 logger.info(msg, extra={...}) 传入）
    """

    # logging.LogRecord 的内置属性，不属于业务 extra 字段
    _BUILTIN_ATTRS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # 用 datetime 格式化时间戳（Windows 的 strftime 不支持 %f 微秒）
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_entry = {
            "ts": dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            log_entry["request_id"] = rid
        # 异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        # 额外字段（logger.info(msg, extra={...}) 中的 extra）
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in self._BUILTIN_ATTRS
        }
        if extra:
            log_entry["extra"] = extra
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """应用 JSON 日志配置到 root logger。

    替代原 logging.basicConfig，将所有日志输出为 JSON 格式。
    uvicorn 的访问日志不受此配置影响（uvicorn 使用自己的 logger）。
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def new_request_id(rid: Optional[str] = None) -> str:
    """生成或设置 request_id 并写入 contextvar。

    Args:
        rid: 指定的 request_id（如从 X-Request-ID 请求头获取）。
             为 None 时自动生成 12 位十六进制 ID。

    Returns:
        最终设置的 request_id。
    """
    if rid is None:
        rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid


def get_request_id() -> Optional[str]:
    """获取当前请求的 request_id（未设置时返回 None）。"""
    return request_id_var.get()
