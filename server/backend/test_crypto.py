"""D1 测试补充：utils/crypto.py 加解密往返测试。

验证：
1. is_encrypted 正确识别 enc:v1: 前缀
2. encrypt_field 对空值/None 原样返回
3. encrypt_field 对已加密值原样返回（幂等）
4. encrypt_field 加密后格式正确（enc:v1: 前缀）
5. decrypt_field 对空值/None/未加密值原样返回
6. decrypt_field 解密 encrypt_field 的结果，与原文一致（往返）
7. 多次加密同一明文产生不同密文（nonce 随机性）
8. 中文字符正确加解密
9. 长字符串正确加解密
"""
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.utils import crypto
from app.utils.crypto import (
    ENC_PREFIX,
    decrypt_field,
    encrypt_field,
    is_encrypted,
)


# 测试用固定密钥（32 字节），避免依赖文件系统
TEST_KEY = b"\x01" * 32
TEST_AESGCM = AESGCM(TEST_KEY)


class CryptoIsEncryptedTests(unittest.TestCase):
    """is_encrypted 识别加密前缀。"""

    def test_identifies_encrypted_value(self):
        self.assertTrue(is_encrypted("enc:v1:abc123"))

    def test_rejects_plain_value(self):
        self.assertFalse(is_encrypted("plaintext"))

    def test_rejects_empty_string(self):
        self.assertFalse(is_encrypted(""))

    def test_rejects_none(self):
        self.assertFalse(is_encrypted(None))

    def test_rejects_value_with_different_prefix(self):
        self.assertFalse(is_encrypted("enc:v2:abc"))
        self.assertFalse(is_encrypted("password123"))


class CryptoEncryptTests(unittest.TestCase):
    """encrypt_field 加密行为。"""

    def setUp(self):
        # mock AESGCM 实例，避免触发 _load_or_create_key
        self._patcher = patch.object(crypto, "_get_aesgcm", return_value=TEST_AESGCM)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_encrypts_plain_string(self):
        result = encrypt_field("hello")
        self.assertTrue(result.startswith(ENC_PREFIX))
        self.assertNotEqual(result, "hello")

    def test_empty_string_returns_empty(self):
        self.assertEqual(encrypt_field(""), "")

    def test_none_returns_empty_string(self):
        self.assertEqual(encrypt_field(None), "")

    def test_already_encrypted_returns_unchanged(self):
        """幂等：已加密的值原样返回，不会双重加密。"""
        encrypted = encrypt_field("hello")
        double_encrypted = encrypt_field(encrypted)
        self.assertEqual(encrypted, double_encrypted)

    def test_each_encryption_produces_different_ciphertext(self):
        """同一明文多次加密产生不同密文（nonce 随机性）。"""
        a = encrypt_field("same plaintext")
        b = encrypt_field("same plaintext")
        self.assertNotEqual(a, b, "相同明文加密结果应不同（nonce 随机）")


class CryptoDecryptTests(unittest.TestCase):
    """decrypt_field 解密行为。"""

    def setUp(self):
        self._patcher = patch.object(crypto, "_get_aesgcm", return_value=TEST_AESGCM)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_empty_string_returns_empty(self):
        self.assertEqual(decrypt_field(""), "")

    def test_none_returns_empty_string(self):
        self.assertEqual(decrypt_field(None), "")

    def test_plain_value_returns_unchanged(self):
        """未加密的明文原样返回（兼容存量数据）。"""
        self.assertEqual(decrypt_field("plaintext"), "plaintext")

    def test_decrypts_encrypted_value(self):
        encrypted = encrypt_field("secret")
        self.assertEqual(decrypt_field(encrypted), "secret")


class CryptoRoundTripTests(unittest.TestCase):
    """encrypt → decrypt 往返测试。"""

    def setUp(self):
        self._patcher = patch.object(crypto, "_get_aesgcm", return_value=TEST_AESGCM)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_roundtrip_ascii(self):
        original = "hello world"
        self.assertEqual(decrypt_field(encrypt_field(original)), original)

    def test_roundtrip_chinese(self):
        original = "你好，世界！加密测试 🔐"
        self.assertEqual(decrypt_field(encrypt_field(original)), original)

    def test_roundtrip_long_string(self):
        original = "x" * 10000
        self.assertEqual(decrypt_field(encrypt_field(original)), original)

    def test_roundtrip_special_chars(self):
        original = "p@ssw0rd!#$%^&*()_+-=[]{}|;':\",./<>?"
        self.assertEqual(decrypt_field(encrypt_field(original)), original)

    def test_roundtrip_smtp_password(self):
        original = "smtp_qq_password_123456"
        self.assertEqual(decrypt_field(encrypt_field(original)), original)


class CryptoFormatTests(unittest.TestCase):
    """加密结果格式校验。"""

    def setUp(self):
        self._patcher = patch.object(crypto, "_get_aesgcm", return_value=TEST_AESGCM)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_encrypted_value_has_prefix(self):
        result = encrypt_field("test")
        self.assertTrue(result.startswith(ENC_PREFIX))

    def test_encrypted_value_is_base64_after_prefix(self):
        """enc:v1: 后面是 base64(nonce|ciphertext)，可被 base64 解码。"""
        import base64
        result = encrypt_field("test")
        encoded = result[len(ENC_PREFIX):]
        # 应能成功 base64 解码
        raw = base64.b64decode(encoded)
        # nonce 12 字节 + 至少 12 字节 ciphertext（AES-GCM tag）
        self.assertGreaterEqual(len(raw), 24)

    def test_encrypted_value_not_equal_to_plaintext(self):
        result = encrypt_field("sensitive_data")
        self.assertNotIn("sensitive_data", result)


if __name__ == "__main__":
    unittest.main()
