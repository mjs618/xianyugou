"""敏感字段加密 - 复刻前端 crypto.ts 的 AES-GCM 256 方案。

前端用 Web Crypto API + non-extractable key；后端用 cryptography 库，
密钥从 data/secret.key 读取（首次随机生成）。加密值带前缀 enc:v1: 以便识别。
"""
from __future__ import annotations
import base64
import os
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import BACKEND_DIR

# 加密值前缀，与前端一致，用于判断字段是否已加密
ENC_PREFIX = "enc:v1:"
_SECRET_KEY_PATH = BACKEND_DIR / "data" / "secret.key"


def _load_or_create_key() -> bytes:
    """加载持久化主密钥；不存在则随机生成 32 字节并写盘。"""
    _SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _SECRET_KEY_PATH.exists():
        return base64.b64decode(_SECRET_KEY_PATH.read_bytes())
    key = secrets.token_bytes(32)  # AES-256
    _SECRET_KEY_PATH.write_bytes(base64.b64encode(key))
    # 仅本用户可读写（类 Unix）
    try:
        os.chmod(_SECRET_KEY_PATH, 0o600)
    except OSError:
        pass
    return key


@lru_cache(maxsize=1)
def _get_aesgcm() -> AESGCM:
    return AESGCM(_load_or_create_key())


def is_encrypted(value: str | None) -> bool:
    """判断字符串是否为加密格式"""
    return bool(value) and value.startswith(ENC_PREFIX)


def encrypt_field(plaintext: str | None) -> str:
    """加密敏感字段，返回 enc:v1:{base64(nonce|ciphertext)}。空值原样返回。"""
    if not plaintext:
        return plaintext or ""
    if is_encrypted(plaintext):
        return plaintext
    aesgcm = _get_aesgcm()
    nonce = secrets.token_bytes(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    encoded = base64.b64encode(nonce + ciphertext).decode("ascii")
    return f"{ENC_PREFIX}{encoded}"


def decrypt_field(value: str | None) -> str:
    """解密字段。未加密/空值原样返回（兼容存量明文）。"""
    if not value or not is_encrypted(value):
        return value or ""
    aesgcm = _get_aesgcm()
    encoded = value[len(ENC_PREFIX):]
    raw = base64.b64decode(encoded)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
