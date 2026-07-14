"""预共享 API Token 生成与校验。

参考 utils/crypto.py 的 _load_or_create_key 模式：
- 首次启动随机生成 token_urlsafe(32) 并写入 data/api.token（0o600 权限）
- 后续启动从文件读取
- 提供 verify_token 用于校验请求头中的 token
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from ..config import BACKEND_DIR

# token 持久化路径，与 secret.key 同目录
_TOKEN_PATH: Path = BACKEND_DIR / "data" / "api.token"


def _load_or_create_token() -> str:
    """加载持久化 token；不存在则随机生成并写盘。

    与 crypto._load_or_create_key 不同：token 不依赖既有数据库存在性，
    缺失时直接生成新的（首次启动场景）。
    """
    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _TOKEN_PATH.exists():
        return _TOKEN_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    _TOKEN_PATH.write_text(token, encoding="utf-8")
    # 仅本用户可读写（类 Unix；Windows 下 chmod 无效但不报错）
    try:
        os.chmod(_TOKEN_PATH, 0o600)
    except OSError:
        pass
    return token


@lru_cache(maxsize=1)
def get_api_token() -> str:
    """获取当前 API token（单例，进程级缓存）。"""
    return _load_or_create_token()


def is_token_configured() -> bool:
    """token 是否已生成（用于 /api/auth/token-status 端点）。"""
    return _TOKEN_PATH.exists()


def verify_token(token: str | None) -> bool:
    """校验给定 token 是否匹配。使用 secrets.compare_digest 防时序攻击。"""
    if not token:
        return False
    expected = get_api_token()
    return secrets.compare_digest(token, expected)
