"""通用工具：日期解析、数值精度、默认设置"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class ConcurrencyError(Exception):
    """乐观锁冲突：传入的 expected_version 与数据库当前 version 不一致。
    router 层应捕获并返回 HTTP 409。"""
    pass


def now_utc() -> datetime:
    """当前 UTC 时间（naive，与 SQLite DateTime 默认一致）。

    使用 timezone-aware API 再剥离时区，等价于已弃用的 datetime.utcnow()，
    避免 Python 3.12+ 的 DeprecationWarning。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """确保 datetime 有时区信息，便于序列化。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_date(value: Any) -> Optional[datetime]:
    """宽松解析日期：支持 datetime / ISO 字符串 / epoch(ms) / None"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # 毫秒时间戳（naive UTC）
        return datetime.fromtimestamp(value / 1000.0, timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # 尝试 ISO 格式（含时区）
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
        # 尝试纯数字时间戳
        if s.isdigit():
            return datetime.fromtimestamp(int(s) / 1000.0, timezone.utc).replace(tzinfo=None)
    return None


def round2(value: float) -> float:
    """保留两位小数（与前端 calcProfit / 返利金额口径一致）"""
    return round(value + 1e-9, 2)


def calc_profit(sale_price: float, cost_price: float) -> float:
    """计算利润，保留两位小数"""
    return round2(sale_price - cost_price)


def calc_warranty_end(start: datetime, days: int) -> datetime:
    """质保到期 = 起算时间 + days 天"""
    return start + timedelta(days=days)


def evaluate_level(
    total_spent: float,
    trade_count: int,
    settings: Any,
) -> str:
    """客户等级自动评定（复刻 customerService.evaluateLevelWithSettings）"""
    if total_spent >= settings.core_threshold or trade_count >= settings.core_trade_count:
        return "core"
    if total_spent >= settings.vip_threshold or trade_count >= settings.vip_trade_count:
        return "vip"
    return "normal"


# 默认设置（与前端 DEFAULT_SETTINGS 一致）
DEFAULT_SETTINGS = {
    "id": 1,
    "warranty_days": 30,
    "rebate_rate": 0.1,
    "rebate_base": "profit",
    "vip_threshold": 500.0,
    "core_threshold": 2000.0,
    "vip_trade_count": 5,
    "core_trade_count": 20,
    "recall_days": 30,
    "backup_path": None,
    "smtp_host": "smtp.qq.com",
    "smtp_port": 465,
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_from": None,
}
