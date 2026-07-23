"""闲鱼 Cookie 解析工具 - 从浏览器复制的原始 Cookie 字符串提取关键字段。

参考 xianyu-auto-reply 项目 common/utils/xianyu_utils.py 的解析思路重写。
关键 Cookie 字段：
- unb: 闲鱼用户 ID（必备，用于区分账号）
- _m_h5_tk: MTOP 签名 token（格式 token_timestamp，取下划线前半段用于签名）
- munb: 手机端用户 ID
"""
import logging
from typing import Optional
from http.cookies import SimpleCookie

logger = logging.getLogger(__name__)


def parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """把原始 Cookie 字符串解析为 {name: value} 字典。

    支持两种格式：
    1. 浏览器复制的 'name1=value1; name2=value2' 格式
    2. DevTools 复制的多行 'name: value' 格式（兼容）
    """
    result: dict[str, str] = {}
    if not cookie_str:
        return result

    # 兼容多行 'name: value' 格式：把换行+冒号转为分号+等号
    normalized = cookie_str.replace("\r", "\n")
    if ":" in normalized and ";" not in normalized:
        # 可能是 DevTools 格式
        lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
        for ln in lines:
            if ":" in ln:
                k, _, v = ln.partition(":")
                k = k.strip()
                v = v.strip()
                if k and v and " " not in k:
                    result[k] = v
        if result:
            return result

    # 标准 'name=value; name=value' 格式
    c = SimpleCookie()
    try:
        c.load(normalized)
        for k, morsel in c.items():
            result[k] = morsel.value
    except Exception as e:
        # SimpleCookie 解析失败时，手动按分号拆分
        logger.debug("SimpleCookie 解析失败，回退手动解析: %s", e)
        for part in normalized.split(";"):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                k, v = k.strip(), v.strip()
                if k:
                    result[k] = v
    return result


def get_unb(cookies: dict[str, str]) -> Optional[str]:
    """提取闲鱼用户 ID（unb）。"""
    return cookies.get("unb") or cookies.get("munb")


def get_token(cookies: dict[str, str]) -> Optional[str]:
    """从 _m_h5_tk 提取签名 token（取下划线前半段）。

    _m_h5_tk 格式: '{token}_{timestamp}'
    """
    raw = cookies.get("_m_h5_tk", "")
    if not raw or "_" not in raw:
        return None
    return raw.split("_")[0]


def validate_cookies(cookie_str: str) -> tuple[bool, Optional[str], str]:
    """校验 Cookie 是否有效（至少包含 unb）。

    返回 (valid, unb, message)
    """
    cookies = parse_cookie_string(cookie_str)
    unb = get_unb(cookies)
    if not unb:
        return (False, None, "Cookie 中缺少 unb 字段（闲鱼用户 ID），请确认已完整复制登录后的 Cookie")
    token = get_token(cookies)
    if not token:
        return (False, unb, "Cookie 中缺少 _m_h5_tk 字段，MTOP 签名将无法工作。建议重新登录闲鱼后再复制完整 Cookie")
    return (True, unb, "Cookie 校验通过")


def cookies_to_header(cookies: dict[str, str]) -> str:
    """把 Cookie 字典转为 HTTP Cookie 请求头值。"""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())
