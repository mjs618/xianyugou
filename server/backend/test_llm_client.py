import json
import unittest

import httpx

from app.services.llm_client import (
    LlmClientError,
    LlmConfig,
    request_chat_completion,
)


class LlmClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = LlmConfig(
            api_base_url="https://model.example/v1",
            api_key="test-api-key",
            model="demo-model",
        )
        self.messages = [
            {"role": "system", "content": "只回答商品问题"},
            {"role": "user", "content": "今天能发货吗"},
        ]

    async def test_chat_completion_sends_minimal_payload_and_returns_trimmed_text(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "  可以，今天发货。  "}}]},
            )

        result = await request_chat_completion(
            self.config,
            self.messages,
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual(result, "可以，今天发货。")
        self.assertEqual(captured["url"], "https://model.example/v1/chat/completions")
        self.assertEqual(captured["authorization"], "Bearer test-api-key")
        self.assertEqual(
            captured["payload"],
            {"model": "demo-model", "messages": self.messages},
        )

    async def test_auth_error_does_not_expose_response_body(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(401, text="secret-provider-body")
        )

        with self.assertRaises(LlmClientError) as raised:
            await request_chat_completion(
                self.config, self.messages, transport=transport
            )

        self.assertEqual(raised.exception.code, "AI_AUTH_FAILED")
        self.assertEqual(raised.exception.status_code, 502)
        self.assertNotIn("secret-provider-body", str(raised.exception))

    async def test_rate_limit_maps_to_stable_error(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(429, text="provider quota detail")
        )

        with self.assertRaises(LlmClientError) as raised:
            await request_chat_completion(
                self.config, self.messages, transport=transport
            )

        self.assertEqual(raised.exception.code, "AI_RATE_LIMITED")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("provider quota detail", str(raised.exception))

    async def test_timeout_maps_to_stable_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("upstream timeout detail", request=request)

        with self.assertRaises(LlmClientError) as raised:
            await request_chat_completion(
                self.config,
                self.messages,
                transport=httpx.MockTransport(handler),
            )

        self.assertEqual(raised.exception.code, "AI_TIMEOUT")
        self.assertEqual(raised.exception.status_code, 504)
        self.assertNotIn("upstream timeout detail", str(raised.exception))

    async def test_invalid_json_maps_to_unavailable_without_body(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="not-json-secret-body")
        )

        with self.assertRaises(LlmClientError) as raised:
            await request_chat_completion(
                self.config, self.messages, transport=transport
            )

        self.assertEqual(raised.exception.code, "AI_INVALID_RESPONSE")
        self.assertNotIn("not-json-secret-body", str(raised.exception))

    async def test_empty_text_is_rejected(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "   "}}]}
            )
        )

        with self.assertRaises(LlmClientError) as raised:
            await request_chat_completion(
                self.config, self.messages, transport=transport
            )

        self.assertEqual(raised.exception.code, "AI_EMPTY_RESPONSE")

    async def test_text_is_limited_to_1000_characters(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "x" * 1200}}]}
            )
        )

        result = await request_chat_completion(
            self.config, self.messages, transport=transport
        )

        self.assertEqual(result, "x" * 1000)


if __name__ == "__main__":
    unittest.main()
