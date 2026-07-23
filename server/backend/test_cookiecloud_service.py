import base64
import hashlib
import json
import unittest

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.services.xianyu.cookiecloud_service import (
    get_cookiecloud_config_status,
    decrypt_cookiecloud_payload,
    extract_cookie_header,
)


def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    out = b""
    prev = b""
    while len(out) < key_len + iv_len:
        prev = hashlib.md5(prev + password + salt).digest()
        out += prev
    return out[:key_len], out[key_len:key_len + iv_len]


def _encrypt_cryptojs_passphrase(plain_text: str, passphrase: str) -> str:
    salt = b"12345678"
    key, iv = _evp_bytes_to_key(passphrase.encode("utf-8"), salt, 32, 16)
    padder = PKCS7(128).padder()
    padded = padder.update(plain_text.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(b"Salted__" + salt + encrypted).decode("ascii")


class CookieCloudServiceTests(unittest.TestCase):
    def test_config_status_lists_missing_entries_and_next_step(self):
        from app.config import settings

        old_values = (
            settings.cookie_cloud_host,
            settings.cookie_cloud_uuid,
            settings.cookie_cloud_password,
            settings.cookie_cloud_domain_keyword,
        )
        settings.cookie_cloud_host = "http://127.0.0.1:8088"
        settings.cookie_cloud_uuid = ""
        settings.cookie_cloud_password = ""
        settings.cookie_cloud_domain_keyword = "goofish.com"
        try:
            status = get_cookiecloud_config_status()
        finally:
            (
                settings.cookie_cloud_host,
                settings.cookie_cloud_uuid,
                settings.cookie_cloud_password,
                settings.cookie_cloud_domain_keyword,
            ) = old_values

        self.assertFalse(status["enabled"])
        self.assertEqual(status["missing_keys"], ["COOKIE_CLOUD_UUID", "COOKIE_CLOUD_PASSWORD"])
        self.assertIn("不会自动续 Cookie", status["message"])
        self.assertIn("COOKIE_CLOUD_UUID", status["next_step"])

    def test_config_status_enabled_when_all_required_entries_exist(self):
        from app.config import settings

        old_values = (
            settings.cookie_cloud_host,
            settings.cookie_cloud_uuid,
            settings.cookie_cloud_password,
            settings.cookie_cloud_domain_keyword,
        )
        settings.cookie_cloud_host = "http://127.0.0.1:8088"
        settings.cookie_cloud_uuid = "uuid-a"
        settings.cookie_cloud_password = "password-a"
        settings.cookie_cloud_domain_keyword = "goofish.com"
        try:
            status = get_cookiecloud_config_status()
        finally:
            (
                settings.cookie_cloud_host,
                settings.cookie_cloud_uuid,
                settings.cookie_cloud_password,
                settings.cookie_cloud_domain_keyword,
            ) = old_values

        self.assertTrue(status["enabled"])
        self.assertEqual(status["missing_keys"], [])
        self.assertIn("会尝试自动续 Cookie", status["message"])

    def test_decrypt_cookiecloud_payload_supports_cryptojs_passphrase_format(self):
        payload = {
            "cookie_data": {
                ".goofish.com": [
                    {"name": "unb", "value": "222"},
                    {"name": "_m_h5_tk", "value": "token_2000"},
                    {"name": "_m_h5_tk_enc", "value": "enc"},
                ],
            },
            "local_storage_data": {},
        }
        uuid = "uuid-a"
        password = "password-a"
        passphrase = hashlib.md5(f"{uuid}-{password}".encode("utf-8")).hexdigest()[:16]
        encrypted = _encrypt_cryptojs_passphrase(json.dumps(payload), passphrase)

        decrypted = decrypt_cookiecloud_payload(uuid, encrypted, password)

        self.assertEqual(decrypted["cookie_data"][".goofish.com"][0]["name"], "unb")

    def test_extract_cookie_header_filters_domain_and_never_includes_other_sites(self):
        payload = {
            "cookie_data": {
                ".goofish.com": [
                    {"name": "unb", "value": "222"},
                    {"name": "_m_h5_tk", "value": "token_2000"},
                ],
                ".example.com": [
                    {"name": "secret", "value": "OTHER_SITE_SENTINEL"},
                ],
            }
        }

        header = extract_cookie_header(payload, domain_keyword="goofish.com")

        self.assertIn("unb=222", header)
        self.assertIn("_m_h5_tk=token_2000", header)
        self.assertNotIn("OTHER_SITE_SENTINEL", header)


if __name__ == "__main__":
    unittest.main()
