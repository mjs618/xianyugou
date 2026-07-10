"""CookieCloud integration for refreshing Goofish cookies.

Only decrypted cookie values are returned to the caller. Do not log values from this module.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from ...config import settings


class CookieCloudError(RuntimeError):
    pass


COOKIECLOUD_REQUIRED_SETTINGS: tuple[tuple[str, str], ...] = (
    ("COOKIE_CLOUD_HOST", "cookie_cloud_host"),
    ("COOKIE_CLOUD_UUID", "cookie_cloud_uuid"),
    ("COOKIE_CLOUD_PASSWORD", "cookie_cloud_password"),
)


def get_cookiecloud_config_status() -> dict[str, Any]:
    missing_keys = [
        env_name
        for env_name, attr_name in COOKIECLOUD_REQUIRED_SETTINGS
        if not str(getattr(settings, attr_name, "") or "").strip()
    ]
    configured_keys = [
        env_name
        for env_name, attr_name in COOKIECLOUD_REQUIRED_SETTINGS
        if str(getattr(settings, attr_name, "") or "").strip()
    ]
    enabled = not missing_keys
    if enabled:
        message = "CookieCloud 已配置完整，Cookie 过期后会尝试自动续 Cookie。"
        next_step = (
            "保持浏览器已登录闲鱼 Web，并通过 CookieCloud 插件同步 goofish.com Cookie；"
            "如遇验证码、滑块或风控，仍需人工处理。"
        )
    else:
        missing_text = "、".join(missing_keys)
        message = f"CookieCloud 未配置完整，Cookie 过期后不会自动续 Cookie。缺少：{missing_text}。"
        next_step = (
            f"在项目根目录 .env 或 Docker Compose 环境变量中补齐 {missing_text}，"
            "然后重启后端；也可以先手动更新账号 Cookie。"
        )
    return {
        "enabled": enabled,
        "configured_keys": configured_keys,
        "missing_keys": missing_keys,
        "domain_keyword": settings.cookie_cloud_domain_keyword,
        "message": message,
        "next_step": next_step,
    }


def is_cookiecloud_configured() -> bool:
    return bool(get_cookiecloud_config_status()["enabled"])


def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    out = b""
    prev = b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + password + salt).digest()
        out += prev
    return out[:key_len], out[key_len:key_len + iv_len]


def _cookiecloud_passphrase(uuid: str, password: str) -> str:
    return hashlib.md5(f"{uuid}-{password}".encode("utf-8")).hexdigest()[:16]


def decrypt_cookiecloud_payload(uuid: str, encrypted: str, password: str) -> dict[str, Any]:
    raw = base64.b64decode(encrypted)
    if not raw.startswith(b"Salted__") or len(raw) < 17:
        raise CookieCloudError("CookieCloud 加密内容格式不支持")
    salt = raw[8:16]
    ciphertext = raw[16:]
    key, iv = _evp_bytes_to_key(_cookiecloud_passphrase(uuid, password).encode("utf-8"), salt, 32, 16)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    try:
        parsed = json.loads(plain.decode("utf-8"))
    except Exception as exc:
        raise CookieCloudError("CookieCloud 解密结果不是有效 JSON") from exc
    if not isinstance(parsed, dict):
        raise CookieCloudError("CookieCloud 解密结果格式异常")
    return parsed


def extract_cookie_header(payload: dict[str, Any], *, domain_keyword: str) -> str:
    cookie_data = payload.get("cookie_data")
    if not isinstance(cookie_data, dict):
        raise CookieCloudError("CookieCloud 数据缺少 cookie_data")

    pairs: list[str] = []
    for domain, cookies in cookie_data.items():
        if domain_keyword not in str(domain):
            continue
        if not isinstance(cookies, list):
            continue
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "").strip()
            if name and value:
                pairs.append(f"{name}={value}")
    if not pairs:
        raise CookieCloudError("CookieCloud 中未找到目标域名 Cookie")
    return "; ".join(pairs)


async def fetch_cookie_header_from_cookiecloud(*, timeout: float = 10.0) -> str:
    if not is_cookiecloud_configured():
        status = get_cookiecloud_config_status()
        raise CookieCloudError(f"CookieCloud 未配置完整：缺少 {'、'.join(status['missing_keys'])}")
    host = settings.cookie_cloud_host.rstrip("/")
    url = f"{host}/get/{settings.cookie_cloud_uuid}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    encrypted = data.get("encrypted") if isinstance(data, dict) else None
    if not encrypted:
        raise CookieCloudError("CookieCloud 响应缺少 encrypted")
    payload = decrypt_cookiecloud_payload(
        settings.cookie_cloud_uuid,
        str(encrypted),
        settings.cookie_cloud_password,
    )
    return extract_cookie_header(
        payload,
        domain_keyword=settings.cookie_cloud_domain_keyword,
    )
