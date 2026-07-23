import unittest
from unittest.mock import patch

import httpx

from app.services.xianyu.mtop_client import MtopClient, MtopError


class _NonJsonAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return httpx.Response(
            200,
            text="<html>COOKIE_SENTINEL TOKEN_SENTINEL raw mtop gateway body</html>",
        )


class ParseErrorSanitizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_json_response_error_does_not_include_raw_response(self):
        client = MtopClient("unb=1; _m_h5_tk=token_1000")

        with patch(
            "app.services.xianyu.mtop_client.httpx.AsyncClient",
            _NonJsonAsyncClient,
        ):
            with self.assertRaises(MtopError) as raised:
                await client.request("mtop.test.api", {"page": 1})

        error_text = str(raised.exception)
        self.assertEqual(error_text, "[PARSE_ERROR] 闲鱼接口响应格式异常，未记录原始响应")
        self.assertNotIn("COOKIE_SENTINEL", error_text)
        self.assertNotIn("TOKEN_SENTINEL", error_text)
        self.assertNotIn("raw mtop gateway body", error_text)


if __name__ == "__main__":
    unittest.main()
