"""OpenAI-compatible Chat Completions 网络边界。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LlmConfig:
    api_base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 20.0


class LlmClientError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def request_chat_completion(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """请求首条文本候选；不记录请求或第三方响应正文。"""
    url = f"{config.api_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": config.model, "messages": messages}

    try:
        async with httpx.AsyncClient(
            timeout=config.timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise LlmClientError(
            "AI_TIMEOUT", "模型服务响应超时，请稍后重试", 504
        ) from exc
    except httpx.RequestError as exc:
        raise LlmClientError(
            "AI_UNAVAILABLE", "模型服务暂时不可用，请稍后重试", 502
        ) from exc

    if response.status_code in {401, 403}:
        raise LlmClientError(
            "AI_AUTH_FAILED", "模型服务认证失败，请检查 API Key", 502
        )
    if response.status_code == 429:
        raise LlmClientError(
            "AI_RATE_LIMITED", "模型服务请求过多，请稍后重试", 503
        )
    if response.status_code >= 400:
        raise LlmClientError(
            "AI_UNAVAILABLE", "模型服务暂时不可用，请稍后重试", 502
        )

    try:
        body: Any = response.json()
    except Exception as exc:
        raise LlmClientError(
            "AI_INVALID_RESPONSE", "模型服务返回格式异常", 502
        ) from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmClientError(
            "AI_INVALID_RESPONSE", "模型服务返回格式异常", 502
        ) from exc
    if not isinstance(content, str):
        raise LlmClientError(
            "AI_INVALID_RESPONSE", "模型服务返回格式异常", 502
        )

    normalized = content.strip()
    if not normalized:
        raise LlmClientError("AI_EMPTY_RESPONSE", "模型服务未生成有效回复", 502)
    return normalized[:1000]
