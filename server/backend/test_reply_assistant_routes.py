import json
import unittest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import (
    OperationLog,
    ProductTemplate,
    ReplyAssistantSettings,
    ReplyRule,
    XianyuAccount,
)
from app.services.llm_client import LlmClientError


class ReplyAssistantRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()

    async def _seed_context(self):
        async with self.Session() as db:
            account = XianyuAccount(
                nickname="主账号",
                cookies="secret-cookie",
                status="online",
            )
            product = ProductTemplate(
                name="测试商品",
                default_cost=7.5,
                default_sale_price=19.9,
            )
            db.add_all([account, product])
            await db.commit()
            return account.id, product.id

    async def test_settings_response_never_exposes_api_key(self):
        async with self.Session() as db:
            db.add(
                ReplyAssistantSettings(
                    id=1,
                    enabled=True,
                    api_key="encrypted-secret",
                )
            )
            await db.commit()

        response = await self.client.get("/api/reply-assistant/settings")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["api_key_configured"])
        self.assertNotIn("api_key", response.json())

    async def test_rule_crud_uses_structured_not_found_error(self):
        _, product_id = await self._seed_context()
        created = await self.client.post(
            "/api/reply-assistant/rules",
            json={
                "name": "价格规则",
                "priority": 10,
                "keywords": [" 价格 ", "价格"],
                "reply_text": "页面价格就是当前售价。",
                "product_template_id": product_id,
            },
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["keywords"], ["价格"])

        rule_id = created.json()["id"]
        updated = await self.client.patch(
            f"/api/reply-assistant/rules/{rule_id}",
            json={"enabled": False},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["enabled"])

        deleted = await self.client.delete(
            f"/api/reply-assistant/rules/{rule_id}"
        )
        self.assertEqual(deleted.status_code, 200)

        missing = await self.client.patch(
            f"/api/reply-assistant/rules/{rule_id}",
            json={"enabled": True},
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"]["code"], "RULE_NOT_FOUND")

    async def test_rule_match_precedes_ai_and_marks_risk(self):
        account_id, product_id = await self._seed_context()
        async with self.Session() as db:
            db.add_all(
                [
                    ReplyAssistantSettings(
                        id=1,
                        enabled=True,
                        ai_enabled=True,
                        api_base_url="https://model.example/v1",
                        api_key="plain-test-key",
                        model="test-model",
                    ),
                    ReplyRule(
                        name="退款规则",
                        priority=5,
                        keywords=["退款"],
                        reply_text="请通过闲鱼订单申请售后。",
                        product_template_id=product_id,
                    ),
                ]
            )
            await db.commit()

        with patch(
            "app.services.reply_assistant_service.request_chat_completion",
            new=AsyncMock(side_effect=AssertionError("规则命中时不应调用 AI")),
        ):
            response = await self.client.post(
                "/api/reply-assistant/suggestions",
                json={
                    "account_id": account_id,
                    "product_template_id": product_id,
                    "buyer_message": "我想退款，怎么处理？",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "rule")
        self.assertEqual(response.json()["risk_level"], "manual_required")
        self.assertIn("退款售后", response.json()["risk_reasons"])

    async def test_ai_suggestion_sends_only_safe_product_fields(self):
        account_id, product_id = await self._seed_context()
        async with self.Session() as db:
            db.add(
                ReplyAssistantSettings(
                    id=1,
                    enabled=True,
                    ai_enabled=True,
                    api_base_url="https://model.example/v1",
                    api_key="plain-test-key",
                    model="test-model",
                    system_prompt="简洁回答",
                )
            )
            await db.commit()

        llm = AsyncMock(return_value="  可以直接下单。 ")
        with patch(
            "app.services.reply_assistant_service.request_chat_completion",
            new=llm,
        ):
            response = await self.client.post(
                "/api/reply-assistant/suggestions",
                json={
                    "account_id": account_id,
                    "product_template_id": product_id,
                    "buyer_message": "还有货吗？",
                    "context_messages": [
                        {"role": "seller", "content": "您好"},
                        {"role": "user", "content": "想了解一下"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "可以直接下单。")
        self.assertEqual(response.json()["source"], "ai")
        config, messages = llm.await_args.args
        serialized = json.dumps(messages, ensure_ascii=False)
        self.assertEqual(config.api_key, "plain-test-key")
        self.assertIn("测试商品", serialized)
        self.assertIn("19.9", serialized)
        self.assertNotIn("7.5", serialized)
        self.assertNotIn("secret-cookie", serialized)

        async with self.Session() as db:
            log = (
                await db.execute(
                    select(OperationLog).where(
                        OperationLog.action == "suggestion_generate"
                    )
                )
            ).scalar_one()
        self.assertNotIn("还有货吗", log.detail or "")
        self.assertNotIn("可以直接下单", log.detail or "")

    async def test_suggestion_validates_switch_account_and_ai_config(self):
        response = await self.client.post(
            "/api/reply-assistant/suggestions",
            json={"account_id": 999, "buyer_message": "你好"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "ASSISTANT_DISABLED")

        account_id, _ = await self._seed_context()
        async with self.Session() as db:
            db.add(ReplyAssistantSettings(id=1, enabled=True, ai_enabled=False))
            await db.commit()

        missing_account = await self.client.post(
            "/api/reply-assistant/suggestions",
            json={"account_id": 999, "buyer_message": "你好"},
        )
        self.assertEqual(missing_account.status_code, 404)
        self.assertEqual(
            missing_account.json()["detail"]["code"], "ACCOUNT_NOT_FOUND"
        )

        no_ai = await self.client.post(
            "/api/reply-assistant/suggestions",
            json={"account_id": account_id, "buyer_message": "你好"},
        )
        self.assertEqual(no_ai.status_code, 409)
        self.assertEqual(no_ai.json()["detail"]["code"], "NO_REPLY_AVAILABLE")

    async def test_ai_context_is_trimmed_and_latest_message_is_preserved(self):
        account_id, _ = await self._seed_context()
        async with self.Session() as db:
            db.add(
                ReplyAssistantSettings(
                    id=1,
                    enabled=True,
                    ai_enabled=True,
                    api_base_url="https://model.example/v1",
                    api_key="plain-test-key",
                    model="test-model",
                    system_prompt="s" * 4000,
                )
            )
            await db.commit()

        llm = AsyncMock(return_value="候选")
        latest = "最新消息" + "新" * 1900
        with patch(
            "app.services.reply_assistant_service.request_chat_completion",
            new=llm,
        ):
            response = await self.client.post(
                "/api/reply-assistant/suggestions",
                json={
                    "account_id": account_id,
                    "buyer_message": latest,
                    "context_messages": [
                        {"role": "user", "content": str(i) * 1000}
                        for i in range(10)
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        _, messages = llm.await_args.args
        self.assertLessEqual(sum(len(item["content"]) for item in messages), 12000)
        self.assertEqual(messages[-1]["content"], latest)
        self.assertNotIn("0" * 1000, [item["content"] for item in messages])

    async def test_llm_error_is_mapped_without_upstream_body(self):
        account_id, _ = await self._seed_context()
        async with self.Session() as db:
            db.add(
                ReplyAssistantSettings(
                    id=1,
                    enabled=True,
                    ai_enabled=True,
                    api_base_url="https://model.example/v1",
                    api_key="plain-test-key",
                    model="test-model",
                )
            )
            await db.commit()

        with patch(
            "app.services.reply_assistant_service.request_chat_completion",
            new=AsyncMock(
                side_effect=LlmClientError(
                    "AI_RATE_LIMITED", "模型服务请求过多，请稍后重试", 503
                )
            ),
        ):
            response = await self.client.post(
                "/api/reply-assistant/suggestions",
                json={"account_id": account_id, "buyer_message": "你好"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "AI_RATE_LIMITED",
                "message": "模型服务请求过多，请稍后重试",
            },
        )


if __name__ == "__main__":
    unittest.main()
