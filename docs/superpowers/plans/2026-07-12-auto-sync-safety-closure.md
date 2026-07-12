# Auto Sync Safety Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 闭环自动同步熔断、手动限频和迁移前备份，使暂停账号不可绕过、已有数据库升级可恢复，并将现有工作区改动按职责验证提交。

**Architecture:** 账号服务提供共享的同步安全断言和手动预检，订单与商品服务在任何网络客户端创建前执行断言，路由仅负责映射明确的 HTTP 状态。迁移器在识别到已有且待升级的 SQLite 数据库后先调用现有备份模块并验证清单，任何备份错误都在 Alembic 写入前终止。

**Tech Stack:** FastAPI、SQLAlchemy AsyncSession、Alembic、SQLite、pytest、React、TypeScript、Vitest、Vite。

---

## File map

- `server/backend/app/services/xianyu/account_service.py`: 共享暂停异常、手动同步限频预检、Cookie 更新状态恢复。
- `server/backend/app/services/xianyu/order_service.py`: 订单同步服务安全门和 MTOP 重试失败分类。
- `server/backend/app/services/xianyu/item_service.py`: 商品同步服务安全门。
- `server/backend/app/routers/xianyu.py`: 409/429/404 API 映射。
- `server/backend/app/maintenance/database_schema.py`: 迁移前备份编排。
- `server/backend/app/main.py`: 健康响应兼容契约。
- `server/backend/test_*.py`: 后端回归与迁移测试。
- `server/backend/Dockerfile`, `server/backend/entrypoint.sh`: 安全自动迁移入口。
- `src/pages/OrderSync.tsx`, `src/services/xianyuService.ts`, `src/types/index.ts`, `tests/services/xianyuService.test.ts`: 自动同步与恢复 UI/API 契约。
- `server/backend/requirements.txt`: Python 3.13 依赖组。
- `vite.config.ts`: vendor 分块组。

### Task 1: 锁定同步安全门的失败行为

**Files:**
- Modify: `server/backend/test_order_service.py`
- Modify: `server/backend/test_xianyu_account_routes.py`
- Modify: `server/backend/test_recover_account.py`
- Modify: `server/backend/test_sync_scheduler.py`

- [ ] **Step 1: 写暂停账号服务测试**

增加两个异步测试：构造 `status="paused"` 的账号，分别调用 `sync_orders_for_account` 与 `sync_items_for_account`；把各模块的 `MtopClient` 替换为一旦构造就失败的桩，断言抛出暂停异常且桩未调用。

- [ ] **Step 2: 写路由限频与状态码测试**

在账号路由测试中令 `last_sync_at=now_utc()`，调用 `POST /api/xianyu/accounts/{id}/sync-orders`，断言 429 且同步函数未调用；暂停账号订单和商品同步均断言 409，不存在账号断言 404。

- [ ] **Step 3: 写恢复与重试分类测试**

断言有效 Cookie 更新会把普通 `invalid`/`risk` 账号恢复为 `online` 并清除错误，但 `paused` 保持暂停；CookieCloud 刷新成功后的普通 `MtopError` 只累计一次 unknown failure，不立即暂停。

- [ ] **Step 4: 运行测试确认 RED**

Run: `python -m pytest server/backend/test_order_service.py server/backend/test_xianyu_account_routes.py server/backend/test_recover_account.py server/backend/test_sync_scheduler.py -q`

Expected: 新增安全断言、429 或状态恢复相关测试失败，既有测试继续通过。

### Task 2: 最小实现同步安全门

**Files:**
- Modify: `server/backend/app/services/xianyu/account_service.py`
- Modify: `server/backend/app/services/xianyu/order_service.py`
- Modify: `server/backend/app/services/xianyu/item_service.py`
- Modify: `server/backend/app/routers/xianyu.py`

- [ ] **Step 1: 定义类型化错误和预检**

在账号服务增加 `XianyuSyncPausedError`、`XianyuSyncRateLimitedError`、`MIN_MANUAL_SYNC_INTERVAL_MINUTES = 60`；`ensure_account_not_paused(account)` 在暂停时抛前者；`ensure_manual_order_sync_allowed(db, account_id)` 检查不存在、暂停以及 `now_utc() - last_sync_at < timedelta(minutes=60)`。

- [ ] **Step 2: 将断言放在网络边界前**

订单和商品同步函数取得账号后、解密 Cookie 或构造 `MtopClient` 前调用 `ensure_account_not_paused`。不要改变现有同账号锁、成功投影或同步日志逻辑。

- [ ] **Step 3: 修正状态与错误分类**

有效 Cookie 更新时，仅当原状态不是 `paused` 才设置 `online`、清空 `last_error` 和连续失败数。重试错误按 `retry_error.risk`、`retry_error.auth_fail`、否则 `unknown` 分类。

- [ ] **Step 4: 映射 API 状态**

订单路由先调用手动预检；限频映射 429、暂停和并发映射 409、不存在映射 404。商品路由把暂停映射 409，不存在仍为 404。

- [ ] **Step 5: 运行聚焦测试确认 GREEN**

Run: `python -m pytest server/backend/test_order_service.py server/backend/test_xianyu_account_routes.py server/backend/test_recover_account.py server/backend/test_sync_scheduler.py -q`

Expected: 全部通过。

- [ ] **Step 6: 提交安全调度功能组**

精确暂存账号模型/schema、调度器、闲鱼路由与服务、对应后端测试、OrderSync 前端/API/类型与测试；提交信息：`feat: enforce safe xianyu auto sync lifecycle`。

### Task 3: 锁定迁移备份和健康契约

**Files:**
- Modify: `server/backend/test_database_migrations.py`
- Modify: `server/backend/test_xianyu_account_routes.py`

- [ ] **Step 1: 写已有库备份测试**

创建临时 SQLite 数据库并升级到旧 revision，调用 `migrate_database`；监听备份函数调用顺序，断言备份及校验发生在 upgrade 前，最终 revision 为 head。

- [ ] **Step 2: 写空库与失败阻断测试**

空库迁移断言不调用备份；让备份函数抛错，断言 `migrate_database` 向上传播且 revision 保持旧值。

- [ ] **Step 3: 写健康响应契约测试**

调用 `/api/health`，断言 `service == "xianyu-backend"`，并且存在布尔型 `scheduler_running`。

- [ ] **Step 4: 运行测试确认 RED**

Run: `python -m pytest server/backend/test_database_migrations.py server/backend/test_xianyu_account_routes.py -q`

Expected: 迁移备份测试和服务名契约测试失败。

### Task 4: 实现迁移前备份并验证容器入口

**Files:**
- Modify: `server/backend/app/maintenance/database_schema.py`
- Modify: `server/backend/app/main.py`
- Modify: `server/backend/Dockerfile`
- Create: `server/backend/entrypoint.sh`
- Create: `server/backend/app/migrations/versions/20260711_01_auto_sync_scheduling.py`

- [ ] **Step 1: 增加备份辅助函数**

从现有 `database_backup` 模块复用 `resolve_sqlite_path`、`create_backup` 和 `verify_backup`。目标目录取 `source.parent.parent / "backups"`，文件名使用 UTC 微秒时间戳；创建后立即验证 manifest。

- [ ] **Step 2: 把备份放在所有已有库写操作前**

`current != head` 时先检查表集合：有表则先备份并验证，再执行 adopt/stamp/upgrade；无表直接从头升级。备份异常不得捕获为成功，也不得先写 Alembic revision。

- [ ] **Step 3: 恢复健康服务名**

在 `HealthResponse` 默认值或 health handler 中恢复 `service="xianyu-backend"`，保留 `scheduler_running`。

- [ ] **Step 4: 运行迁移和健康测试确认 GREEN**

Run: `python -m pytest server/backend/test_database_migrations.py server/backend/test_xianyu_account_routes.py -q`

Expected: 全部通过；临时数据库升级到 head，失败用例 revision 不变。

- [ ] **Step 5: 静态验证入口文件**

Run: `git diff --check -- server/backend/Dockerfile server/backend/entrypoint.sh server/backend/app/maintenance/database_schema.py server/backend/app/migrations/versions/20260711_01_auto_sync_scheduling.py`

Expected: 无输出、退出码 0。Docker daemon 不可用时不启动真实容器。

- [ ] **Step 6: 提交迁移组**

精确暂存迁移器、revision、entrypoint、Dockerfile 和迁移测试；提交信息：`feat: back up database before automatic migration`。

### Task 5: 分组验证独立维护改动

**Files:**
- Modify: `server/backend/app/services/xianyu/order_parser.py`
- Modify: `server/backend/app/utils/helpers.py`
- Modify: `server/backend/requirements.txt`
- Modify: `vite.config.ts`
- Modify: related finance/parser tests already changed in the worktree

- [ ] **Step 1: 验证并提交 datetime 兼容组**

Run: `python -m pytest server/backend/test_xianyu_order_parser.py server/backend/test_expense_finance_service.py -q`

Expected: 全部通过。精确暂存 datetime 相关源文件和测试，提交：`refactor: use timezone-aware datetime helpers`。

- [ ] **Step 2: 验证并提交 Python 依赖组**

Run: `python -m pip check`

Expected: `No broken requirements found.` 再运行后端全量测试。仅在声明版本与已验证运行时兼容时提交 `requirements.txt`，提交：`build: update backend dependencies for Python 3.13`。

- [ ] **Step 3: 验证并提交 Vite 分块组**

Run: `npm run build`

Expected: 构建成功，主入口 chunk 不超过配置阈值；精确暂存 `vite.config.ts`，提交：`build: split frontend vendor chunks`。

### Task 6: 全量验收与记忆收尾

**Files:**
- Modify: `E:\Obsidian\Codex\projects\XianyuGou.md`

- [ ] **Step 1: 后端全量测试**

Run: `python -m pytest server/backend -q`

Expected: 全部测试和 subtests 通过。

- [ ] **Step 2: 前端测试、类型与构建**

Run: `npm test -- --run`

Run: `npx tsc --noEmit`

Run: `npm run build`

Expected: 三项均退出码 0；若根目录扫描遇到沙箱不可读缓存，仅对验证命令申请所需权限，不修改业务配置规避。

- [ ] **Step 3: 审计提交与工作区**

Run: `git status --short`

Run: `git log --oneline -8`

Expected: 所有本轮改动均进入职责清晰的提交；无意外文件被暂存或遗漏。

- [ ] **Step 4: 更新持久记忆**

在 `E:\Obsidian\Codex\projects\XianyuGou.md` 记录安全边界、迁移备份策略、提交、验证结果与 Docker 未验证事项；不写入任何 Cookie、密钥或凭证。
