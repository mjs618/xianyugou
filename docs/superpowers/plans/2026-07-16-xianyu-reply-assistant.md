# Xianyu Reply Assistant MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有本地优先系统中增加规则优先、AI 可选、始终人工确认的闲鱼回复助手 MVP。

**Architecture:** 后端新增独立的回复助手模型、服务、LLM 客户端和路由，复用现有账号、商品模板、字段加密和操作审计边界。前端新增一个一级页面和单独 service；页面只生成、编辑和复制候选，不读取 Cookie、不调用闲鱼 MTOP/IM，也不自动发送。

**Tech Stack:** FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、httpx、React 18、TypeScript、Ant Design、Vitest、Testing Library、Playwright。

---

## 文件结构

- `server/backend/app/models/reply_assistant.py`：回复助手单例配置与固定回复规则 ORM。
- `server/backend/app/schemas/reply_assistant.py`：配置、规则、上下文和候选 API 契约。
- `server/backend/app/services/reply_assistant_service.py`：配置/规则 CRUD、规则匹配、风险识别和建议编排。
- `server/backend/app/services/llm_client.py`：OpenAI-compatible Chat Completions 唯一网络边界。
- `server/backend/app/routers/reply_assistant.py`：REST 路由和业务错误到 HTTP 的映射。
- `server/backend/app/migrations/versions/20260716_01_reply_assistant.py`：两张新表的显式迁移。
- `server/backend/test_reply_assistant_service.py`：配置、规则、风险和编排单元测试。
- `server/backend/test_llm_client.py`：模型请求、响应和错误脱敏测试。
- `server/backend/test_reply_assistant_routes.py`：路由 CRUD、建议生成和认证边界测试。
- `src/services/replyAssistantService.ts`：前端类型、日期归一化和 API 调用。
- `src/pages/reply-assistant/ReplyAssistantPage.tsx`：页面数据加载与交互编排。
- `src/pages/reply-assistant/ReplyComposer.tsx`：候选输入、结果、风险提示和复制。
- `src/pages/reply-assistant/ReplyAssistantConfig.tsx`：AI 配置和规则管理抽屉。
- `tests/services/replyAssistantService.test.ts`：前端 service 契约测试。
- `tests/components/ReplyAssistantPage.test.tsx`：页面行为测试。
- `tests/e2e/ui-foundation.spec.ts`：真实路由冒烟和移动完整导航覆盖。

## Task 1: Persistence and migration

**Files:**
- Create: `server/backend/app/models/reply_assistant.py`
- Modify: `server/backend/app/models/__init__.py`
- Create: `server/backend/app/migrations/versions/20260716_01_reply_assistant.py`
- Modify: `server/backend/test_database_migrations.py`

- [ ] **Step 1: Write the failing metadata and migration test**

Append a test that upgrades a database from `20260713_02` and asserts both tables and the non-secret columns exist:

```python
def test_reply_assistant_migration_adds_settings_and_rules(tmp_path):
    database = tmp_path / "reply-assistant.db"
    url = f"sqlite:///{database.as_posix()}"
    command.upgrade(migration_config(url), "20260713_02")
    command.upgrade(migration_config(url), "head")

    engine = create_engine(url)
    inspector = inspect(engine)
    assert {"reply_assistant_settings", "reply_rules"} <= set(inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("reply_assistant_settings")} >= {
        "id", "enabled", "ai_enabled", "api_base_url", "api_key", "model", "system_prompt"
    }
    engine.dispose()
```

- [ ] **Step 2: Run the migration test and verify RED**

Run: `python -m pytest server/backend/test_database_migrations.py::test_reply_assistant_migration_adds_settings_and_rules -q`

Expected: FAIL because revision `20260716_01` and the tables do not exist.

- [ ] **Step 3: Add the two ORM models and migration**

Implement these model contracts with `TimestampMixin`:

```python
class ReplyAssistantSettings(TimestampMixin, Base):
    __tablename__ = "reply_assistant_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    api_base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ReplyRule(TimestampMixin, Base):
    __tablename__ = "reply_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", index=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    product_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("product_templates.id", ondelete="CASCADE"), nullable=True, index=True
    )
```

Migration revision is `20260716_01`, down revision is `20260713_02`, creates both tables and indexes, and drops them in reverse order on downgrade.

- [ ] **Step 4: Run migration tests and verify GREEN**

Run: `python -m pytest server/backend/test_database_migrations.py -q`

Expected: all database migration tests pass.

- [ ] **Step 5: Commit persistence**

```bash
git add server/backend/app/models/reply_assistant.py server/backend/app/models/__init__.py server/backend/app/migrations/versions/20260716_01_reply_assistant.py server/backend/test_database_migrations.py
git commit -m "feat(reply): add reply assistant persistence"
```

## Task 2: Settings and rule service

**Files:**
- Create: `server/backend/app/schemas/reply_assistant.py`
- Modify: `server/backend/app/schemas/__init__.py`
- Create: `server/backend/app/services/reply_assistant_service.py`
- Create: `server/backend/test_reply_assistant_service.py`

- [ ] **Step 1: Write failing service tests**

Cover these exact behaviors:

```python
async def test_update_settings_encrypts_key_and_public_view_masks_it(session):
    await update_settings(session, ReplyAssistantSettingsUpdate(api_key="secret", model="demo"))
    stored = await get_settings(session)
    assert stored.api_key != "secret"
    assert decrypt_field(stored.api_key) == "secret"
    assert (await get_public_settings(session)).api_key_configured is True


async def test_blank_key_preserves_existing_and_clear_flag_removes_it(session):
    await update_settings(session, ReplyAssistantSettingsUpdate(api_key="secret"))
    await update_settings(session, ReplyAssistantSettingsUpdate(api_key=""))
    assert decrypt_field((await get_settings(session)).api_key) == "secret"
    await update_settings(session, ReplyAssistantSettingsUpdate(clear_api_key=True))
    assert (await get_settings(session)).api_key == ""


async def test_product_rule_wins_then_priority_and_id(session):
    # create one generic high-priority rule and one product-scoped lower-priority rule
    matched = await match_rule(session, buyer_message="现在能发货吗", product_template_id=7)
    assert matched.name == "商品专属"


def test_sensitive_intent_is_manual_required():
    level, reasons = classify_risk("最低价多少，可以私下转账吗")
    assert level == "manual_required"
    assert {"议价", "私下付款"} <= set(reasons)
```

Use an in-memory SQLite session created with `Base.metadata.create_all` so encryption and ordering are tested against real ORM behavior.

- [ ] **Step 2: Run service tests and verify RED**

Run: `python -m pytest server/backend/test_reply_assistant_service.py -q`

Expected: collection/import failure because schemas and service do not exist.

- [ ] **Step 3: Implement schemas and minimal service**

Define:

```python
class ReplyAssistantSettingsUpdate(BaseModel):
    enabled: bool | None = None
    ai_enabled: bool | None = None
    api_base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    model: str | None = Field(default=None, max_length=100)
    system_prompt: str | None = Field(default=None, max_length=4000)


class ReplyRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    priority: int = Field(default=0, ge=-1000, le=1000)
    keywords: list[str] = Field(min_length=1, max_length=20)
    reply_text: str = Field(min_length=1, max_length=1000)
    product_template_id: int | None = None
```

Service functions are `get_settings`, `get_public_settings`, `update_settings`, `list_rules`, `create_rule`, `update_rule`, `delete_rule`, `match_rule`, and `classify_risk`. Normalize keywords with `casefold()`, trim, remove duplicates, reject items over 50 characters, and order product-specific rules before generic rules.

Validate `api_base_url` with `urllib.parse.urlparse`: allow HTTPS or HTTP only when hostname is `localhost` or `127.0.0.1`. Log only changed field names through `log_operation`.

- [ ] **Step 4: Run service tests and verify GREEN**

Run: `python -m pytest server/backend/test_reply_assistant_service.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit settings and rules**

```bash
git add server/backend/app/schemas/reply_assistant.py server/backend/app/schemas/__init__.py server/backend/app/services/reply_assistant_service.py server/backend/test_reply_assistant_service.py
git commit -m "feat(reply): add settings and reply rules"
```

## Task 3: LLM network boundary

**Files:**
- Create: `server/backend/app/services/llm_client.py`
- Create: `server/backend/test_llm_client.py`

- [ ] **Step 1: Write failing httpx transport tests**

Use `httpx.MockTransport` to prove the client sends only the configured model/messages and maps errors without response bodies:

```python
async def test_chat_completion_returns_trimmed_first_text():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json={"choices": [{"message": {"content": "  可以，今天发货。  "}}]}
    ))
    result = await request_chat_completion(config, messages, transport=transport)
    assert result == "可以，今天发货。"


async def test_auth_error_does_not_expose_body():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="secret-provider-body"))
    with pytest.raises(LlmClientError) as exc:
        await request_chat_completion(config, messages, transport=transport)
    assert exc.value.code == "AI_AUTH_FAILED"
    assert "secret-provider-body" not in str(exc.value)
```

Also cover 429, timeout, invalid JSON, empty text and 1000-character output truncation.

- [ ] **Step 2: Run LLM tests and verify RED**

Run: `python -m pytest server/backend/test_llm_client.py -q`

Expected: import failure because `llm_client.py` does not exist.

- [ ] **Step 3: Implement the isolated client**

Define immutable config and stable exception types:

```python
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
```

`request_chat_completion` posts to `{base}/chat/completions`, uses `Authorization: Bearer`, never logs payload or response body, performs no retry, and accepts an optional transport only for tests.

- [ ] **Step 4: Run LLM tests and verify GREEN**

Run: `python -m pytest server/backend/test_llm_client.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the client**

```bash
git add server/backend/app/services/llm_client.py server/backend/test_llm_client.py
git commit -m "feat(reply): add sanitized LLM client"
```

## Task 4: Suggestion orchestration and REST routes

**Files:**
- Modify: `server/backend/app/services/reply_assistant_service.py`
- Create: `server/backend/app/routers/reply_assistant.py`
- Modify: `server/backend/app/main.py`
- Create: `server/backend/test_reply_assistant_routes.py`

- [ ] **Step 1: Write failing route tests**

Build an in-memory application DB override and cover:

```python
async def test_rule_suggestion_never_calls_llm(client, seeded_account, seeded_rule, monkeypatch):
    monkeypatch.setattr(reply_assistant_service, "request_chat_completion", AsyncMock(side_effect=AssertionError))
    response = await client.post("/api/reply-assistant/suggestions", json={
        "account_id": seeded_account.id,
        "buyer_message": "现在能发货吗",
        "context_messages": [],
    })
    assert response.status_code == 200
    assert response.json()["source"] == "rule"


async def test_missing_rule_and_disabled_ai_returns_422(client, seeded_account):
    response = await client.post("/api/reply-assistant/suggestions", json={
        "account_id": seeded_account.id,
        "buyer_message": "没有规则能匹配这句话",
        "context_messages": [],
    })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NO_REPLY_AVAILABLE"


async def test_settings_response_never_contains_api_key(client):
    await client.put("/api/reply-assistant/settings", json={"api_key": "test-secret-key"})
    response = await client.get("/api/reply-assistant/settings")
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is True
    assert "api_key" not in response.json()
```

The same test module must also create a product template with `default_cost=99` and `default_sale_price=199`, patch `request_chat_completion`, and assert the generated model messages contain `199` but contain neither `99` nor the account Cookie. Add one paused account case expecting 200, one soft-deleted account case expecting 404, and one audit query asserting the serialized detail contains neither the buyer message nor returned reply. CRUD tests cover settings GET/PUT and rules list/create/patch/delete.

- [ ] **Step 2: Run route tests and verify RED**

Run: `python -m pytest server/backend/test_reply_assistant_routes.py -q`

Expected: 404/import failure because router and orchestration are absent.

- [ ] **Step 3: Implement orchestration and router**

Add `generate_suggestion(db, request)` with this fixed order:

```python
settings = await get_settings(db)
require_assistant_enabled(settings)
account = await require_active_account_record(db, request.account_id)  # paused allowed, deleted rejected
product = await optional_product_template(db, request.product_template_id)
risk_level, risk_reasons = classify_risk(request.buyer_message)
rule = await match_rule(db, request.buyer_message, request.product_template_id)
if rule:
    return rule_response(rule, risk_level, risk_reasons)
require_ai_ready(settings)
messages = build_messages(settings.system_prompt, product, request)
reply = await request_chat_completion(llm_config(settings), messages)
return ai_response(reply, risk_level, risk_reasons)
```

Limit accumulated context to 12000 characters by dropping oldest context first. Audit detail is JSON containing only `account_id`, `product_template_id`, `source`, `risk_level`, and `matched_rule_id`.

Map `ReplyAssistantError` and `LlmClientError` to `HTTPException` with structured `detail={"code": exc.code, "message": exc.message}` and commit successful writes once per route.

- [ ] **Step 4: Run backend reply tests and verify GREEN**

Run: `python -m pytest server/backend/test_reply_assistant_service.py server/backend/test_llm_client.py server/backend/test_reply_assistant_routes.py -q`

Expected: all reply assistant backend tests pass.

- [ ] **Step 5: Commit API orchestration**

```bash
git add server/backend/app/services/reply_assistant_service.py server/backend/app/routers/reply_assistant.py server/backend/app/main.py server/backend/test_reply_assistant_routes.py
git commit -m "feat(reply): expose reply assistant API"
```

## Task 5: Frontend service contract

**Files:**
- Modify: `src/types/index.ts`
- Create: `src/services/replyAssistantService.ts`
- Create: `tests/services/replyAssistantService.test.ts`

- [ ] **Step 1: Write failing service tests**

```typescript
it('never sends an api key on settings reads', async () => {
  setMockResponse('get', '/api/reply-assistant/settings', settingsResponse);
  const result = await getReplyAssistantSettings();
  expect(result.api_key_configured).toBe(true);
  expect(result).not.toHaveProperty('api_key');
});

it('posts the exact suggestion input', async () => {
  setMockResponse('post', '/api/reply-assistant/suggestions', suggestionResponse);
  await generateReplySuggestion(input);
  expect(getMockCalls('post', '/api/reply-assistant/suggestions')[0].body).toEqual(input);
});
```

Also test settings update, rule CRUD, date normalization and structured error message extraction.

- [ ] **Step 2: Run service tests and verify RED**

Run: `npm test -- --run tests/services/replyAssistantService.test.ts`

Expected: module import failure.

- [ ] **Step 3: Implement types and service**

Export `ReplyAssistantSettings`, `ReplyRule`, `ReplyContextMessage`, `ReplySuggestionInput`, and `ReplySuggestion`. Service methods are `getReplyAssistantSettings`, `updateReplyAssistantSettings`, `listReplyRules`, `createReplyRule`, `updateReplyRule`, `deleteReplyRule`, and `generateReplySuggestion`.

Only settings update accepts `api_key`; settings response type does not contain it.

- [ ] **Step 4: Run service tests and verify GREEN**

Run: `npm test -- --run tests/services/replyAssistantService.test.ts`

Expected: all service tests pass.

- [ ] **Step 5: Commit frontend service**

```bash
git add src/types/index.ts src/services/replyAssistantService.ts tests/services/replyAssistantService.test.ts
git commit -m "feat(reply): add frontend reply service"
```

## Task 6: Reply assistant page and navigation

**Files:**
- Create: `src/pages/reply-assistant/ReplyComposer.tsx`
- Create: `src/pages/reply-assistant/ReplyAssistantConfig.tsx`
- Create: `src/pages/reply-assistant/ReplyAssistantPage.tsx`
- Modify: `src/router.tsx`
- Modify: `src/utils/layoutNavigation.ts`
- Modify: `src/layouts/MainLayout.tsx`
- Modify: `tests/utils/layoutNavigation.test.ts`
- Create: `tests/components/ReplyAssistantPage.test.tsx`

- [ ] **Step 1: Write failing page and navigation tests**

Page tests mock `replyAssistantService`, `xianyuService`, and `productTemplateService` and assert:

```typescript
it('generates, edits and copies a rule suggestion', async () => {
  render(<ReplyAssistantPage />);
  await user.selectOptions(screen.getByLabelText('闲鱼账号'), '1');
  await user.type(screen.getByLabelText('买家消息'), '现在能发货吗');
  await user.click(screen.getByRole('button', { name: '生成候选' }));
  expect(await screen.findByText('固定规则')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '复制候选' }));
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith('可以，今天发货。');
});

it('shows manual review warning and preserves input after errors', async () => {
  generateReplySuggestionMock
    .mockResolvedValueOnce({ reply: '需要人工核对', source: 'ai', risk_level: 'manual_required', risk_reasons: ['退款'], copy_allowed: true })
    .mockRejectedValueOnce(new Error('模型暂时不可用'));
  render(<ReplyAssistantPage />);
  await user.selectOptions(screen.getByLabelText('闲鱼账号'), '1');
  const input = screen.getByLabelText('买家消息');
  await user.type(input, '我要退款');
  await user.click(screen.getByRole('button', { name: '生成候选' }));
  expect(await screen.findByText('需要人工核对')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '生成候选' }));
  expect(await screen.findByText('模型暂时不可用')).toBeInTheDocument();
  expect(input).toHaveValue('我要退款');
});

it('keeps api key blank while showing configured state', async () => {
  render(<ReplyAssistantPage />);
  await user.click(screen.getByRole('button', { name: '配置回复助手' }));
  expect(await screen.findByText('密钥已配置')).toBeInTheDocument();
  expect(screen.getByLabelText('API Key')).toHaveValue('');
});
```

Update navigation expectation to include `/reply-assistant` before `/order-sync`.

- [ ] **Step 2: Run page tests and verify RED**

Run: `npm test -- --run tests/components/ReplyAssistantPage.test.tsx tests/utils/layoutNavigation.test.ts`

Expected: imports/routes fail because the page is absent.

- [ ] **Step 3: Implement the focused components**

`ReplyComposer` owns only form and result state. `ReplyAssistantConfig` owns settings/rule editing. `ReplyAssistantPage` loads accounts, active templates, settings and rules, then passes callbacks down.

Use Ant Design `Form`, `Select`, `Input.TextArea`, `Alert`, `Tag`, `Drawer`, `Table`, and `Modal`. Disable generation until account and nonblank buyer message are present. Show paused account status but do not disable it. Copy uses `navigator.clipboard.writeText` only and never calls a backend send endpoint.

Add lazy route `/reply-assistant`, label “回复助手”, and `MessageOutlined` icon. Include it in desktop navigation and the mobile full drawer, but do not add it to the five-item mobile quick bar.

- [ ] **Step 4: Run page tests and verify GREEN**

Run: `npm test -- --run tests/components/ReplyAssistantPage.test.tsx tests/utils/layoutNavigation.test.ts`

Expected: all targeted UI tests pass.

- [ ] **Step 5: Commit page and navigation**

```bash
git add src/pages/reply-assistant src/router.tsx src/utils/layoutNavigation.ts src/layouts/MainLayout.tsx tests/components/ReplyAssistantPage.test.tsx tests/utils/layoutNavigation.test.ts
git commit -m "feat(reply): add reply assistant workspace"
```

## Task 7: E2E, security regression and full verification

**Files:**
- Modify: `tests/e2e/ui-foundation.spec.ts`
- Modify only if tests expose a defect: files introduced in Tasks 1–6

- [ ] **Step 1: Extend API mocks and write failing E2E**

Add mock responses for accounts, templates, reply settings, rules and suggestions. Add a test that unlocks, opens `/reply-assistant`, generates a rule candidate, sees the source tag, and confirms the manual-review alert for a refund message. Extend the mobile navigation test to assert “回复助手” is reachable.

- [ ] **Step 2: Run E2E and verify RED/GREEN transition**

Run: `npm run test:e2e -- tests/e2e/ui-foundation.spec.ts`

Expected before the E2E mock additions: FAIL because reply-assistant API responses are missing. After adding the exact mocks described in Step 1, rerun and expect all Chromium cases to pass without production-code changes.

- [ ] **Step 3: Run backend full suite**

Run: `python -m pytest server/backend -q`

Expected: all backend tests pass with no real model or闲鱼 network access.

- [ ] **Step 4: Run frontend full suite and production build**

Run: `npm test -- --run`

Expected: all Vitest files pass.

Run: `npm run build`

Expected: exit 0; existing Vite chunk-size and `use client` warnings are acceptable.

- [ ] **Step 5: Run security and diff checks**

```bash
git diff --check
git grep -n -E 'sk-[A-Za-z0-9_-]{16,}|api_key.*=.*[A-Za-z0-9]{20,}' -- ':!docs/superpowers/*' ':!tests/*'
```

Expected: no whitespace errors and no committed secrets. Inspect the final diff to ensure no MTOP, Cookie, WebSocket or automated-send code was added.

- [ ] **Step 6: Commit E2E and final fixes**

```bash
git add tests/e2e/ui-foundation.spec.ts
git commit -m "test(reply): verify reply assistant workflow"
```

- [ ] **Step 7: Deployment gate**

Do not rebuild Docker automatically. Report passing code-level verification and ask for a separate deployment confirmation because the migration will modify the real database after a pre-migration backup.
