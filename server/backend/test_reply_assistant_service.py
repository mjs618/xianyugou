import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models import ProductTemplate, ReplyAssistantSettings, ReplyRule, XianyuAccount
from app.schemas.reply_assistant import (
    ReplyAssistantSettingsUpdate,
    ReplyRuleCreate,
    ReplySuggestionRequest,
)
from app.services import reply_assistant_service
from app.services.reply_assistant_service import (
    ReplyAssistantError,
    check_reply_risk,
    classify_risk,
    create_rule,
    generate_suggestion,
    get_public_settings,
    get_settings,
    match_rule,
    update_settings,
)
from app.utils import crypto
from app.utils.crypto import decrypt_field


TEST_AESGCM = AESGCM(b"\x02" * 32)


class ReplyAssistantServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self.crypto_patcher = patch.object(
            crypto, "_get_aesgcm", return_value=TEST_AESGCM
        )
        self.crypto_patcher.start()

    async def asyncTearDown(self):
        self.crypto_patcher.stop()
        await self.engine.dispose()

    async def test_update_settings_encrypts_key_and_public_view_masks_it(self):
        async with self.Session() as session:
            await update_settings(
                session,
                ReplyAssistantSettingsUpdate(api_key="secret", model="demo"),
            )
            stored = await get_settings(session)
            public = await get_public_settings(session)

        self.assertNotEqual(stored.api_key, "secret")
        self.assertEqual(decrypt_field(stored.api_key), "secret")
        self.assertTrue(public.api_key_configured)
        self.assertFalse(hasattr(public, "api_key"))

    async def test_blank_key_preserves_existing_and_clear_flag_removes_it(self):
        async with self.Session() as session:
            await update_settings(
                session, ReplyAssistantSettingsUpdate(api_key="secret")
            )
            await update_settings(session, ReplyAssistantSettingsUpdate(api_key=""))
            self.assertEqual(
                decrypt_field((await get_settings(session)).api_key), "secret"
            )
            await update_settings(
                session, ReplyAssistantSettingsUpdate(clear_api_key=True)
            )
            self.assertEqual((await get_settings(session)).api_key, "")

    async def test_product_rule_wins_before_generic_rule(self):
        async with self.Session() as session:
            session.add(
                ProductTemplate(
                    id=7,
                    name="测试商品",
                    default_cost=10,
                    default_sale_price=20,
                    warranty_days=30,
                )
            )
            await session.flush()
            await create_rule(
                session,
                ReplyRuleCreate(
                    name="通用高优先级",
                    priority=100,
                    keywords=["发货"],
                    reply_text="通用回复",
                ),
            )
            await create_rule(
                session,
                ReplyRuleCreate(
                    name="商品专属",
                    priority=1,
                    keywords=["发货"],
                    reply_text="商品回复",
                    product_template_id=7,
                ),
            )
            matched = await match_rule(
                session,
                buyer_message="现在能发货吗",
                product_template_id=7,
            )

        self.assertIsNotNone(matched)
        self.assertEqual(matched.name, "商品专属")

    async def test_same_scope_orders_by_priority_then_id(self):
        async with self.Session() as session:
            first = ReplyRule(
                name="低优先级",
                enabled=True,
                priority=1,
                keywords=["发货"],
                reply_text="低",
            )
            second = ReplyRule(
                name="高优先级先创建",
                enabled=True,
                priority=2,
                keywords=["发货"],
                reply_text="高一",
            )
            third = ReplyRule(
                name="高优先级后创建",
                enabled=True,
                priority=2,
                keywords=["发货"],
                reply_text="高二",
            )
            session.add_all([first, second, third])
            await session.flush()
            matched = await match_rule(
                session, buyer_message="发货时间", product_template_id=None
            )

        self.assertEqual(matched.id, second.id)

    async def test_create_rule_normalizes_and_deduplicates_keywords(self):
        async with self.Session() as session:
            rule = await create_rule(
                session,
                ReplyRuleCreate(
                    name="归一化",
                    keywords=[" 发货 ", "发货", "SHIP", "ship"],
                    reply_text="可以发货",
                ),
            )

        self.assertEqual(rule.keywords, ["发货", "ship"])

    async def test_create_rule_rejects_keyword_over_50_characters(self):
        async with self.Session() as session:
            with self.assertRaisesRegex(ReplyAssistantError, "50"):
                await create_rule(
                    session,
                    ReplyRuleCreate(
                        name="过长",
                        keywords=["x" * 51],
                        reply_text="回复",
                    ),
                )

    def test_sensitive_intent_is_manual_required(self):
        level, reasons = classify_risk("最低价多少，可以私下转账吗")

        self.assertEqual(level, "manual_required")
        self.assertTrue({"议价", "私下付款"}.issubset(set(reasons)))

    async def test_generate_suggestion_merges_risk_from_buyer_and_reply(self):
        async with self.Session() as session:
            session.add_all(
                [
                    XianyuAccount(id=1, nickname="主账号", cookies="c", status="online"),
                    ProductTemplate(
                        id=7,
                        name="测试商品",
                        default_cost=10,
                        default_sale_price=20,
                    ),
                    ReplyAssistantSettings(
                        id=1,
                        enabled=True,
                        ai_enabled=True,
                    ),
                    ReplyRule(
                        name="售后固定回复",
                        enabled=True,
                        priority=10,
                        keywords=["发货"],
                        reply_text="如需退款请通过闲鱼订单申请售后。",
                        product_template_id=7,
                    ),
                ]
            )
            await session.commit()
            result = await generate_suggestion(
                session,
                ReplySuggestionRequest(
                    account_id=1,
                    product_template_id=7,
                    buyer_message="什么时候发货",
                ),
            )

        self.assertEqual(result.source, "rule")
        self.assertEqual(result.risk_level, "manual_required")
        self.assertIn("退款售后", result.risk_reasons)

    async def test_generate_suggestion_dedupes_overlapping_risk_reasons(self):
        async with self.Session() as session:
            session.add_all(
                [
                    XianyuAccount(id=1, nickname="主账号", cookies="c", status="online"),
                    ReplyAssistantSettings(
                        id=1,
                        enabled=True,
                        ai_enabled=True,
                    ),
                    ReplyRule(
                        name="退款引导",
                        enabled=True,
                        priority=10,
                        keywords=["退款"],
                        reply_text="退款请点击订单页面申请退货。",
                    ),
                ]
            )
            await session.commit()
            result = await generate_suggestion(
                session,
                ReplySuggestionRequest(
                    account_id=1,
                    buyer_message="我要退款退货",
                ),
            )

        self.assertEqual(result.risk_level, "manual_required")
        self.assertEqual(result.risk_reasons.count("退款售后"), 1)

    def test_check_reply_risk_returns_normal_for_safe_text(self):
        level, reasons = check_reply_risk("您好，今天可以发货。")

        self.assertEqual(level, "normal")
        self.assertEqual(reasons, [])

    def test_check_reply_risk_trims_and_classifies_risk_text(self):
        level, reasons = check_reply_risk("  请提供电话和身份证  ")

        self.assertEqual(level, "manual_required")
        self.assertTrue({"隐私认证"}.issubset(set(reasons)))

    async def test_remote_http_api_base_url_is_rejected(self):
        async with self.Session() as session:
            with self.assertRaisesRegex(ReplyAssistantError, "HTTPS"):
                await update_settings(
                    session,
                    ReplyAssistantSettingsUpdate(
                        api_base_url="http://example.com/v1"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
