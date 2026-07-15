# UI Foundation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐现有闲鱼记账系统的认证入口、移动导航、防丢、运行状态、可访问性与关键 E2E，使核心业务模块形成可进入、可发现、可恢复的使用闭环。

**Architecture:** 在根节点用 `AuthGate` 统一阻止未认证业务路由挂载，通过 `apiClient` 的 401 事件回收失效会话；在 `MainLayout` 集中补移动全导航与语义结构。表单防丢使用独立 hook，系统状态只消费既有 `/api/metrics`，E2E 全部使用网络拦截的假数据。

**Tech Stack:** React 18、React Router 6、Ant Design 5、Zustand、TypeScript、Vitest、Testing Library、Playwright、Vite。

---

## Progress

- [x] 设计范围、非目标与确认边界已收敛
- [x] 已核对脏工作区与重叠文件，不回退现有改动
- [x] P0 统一认证解锁入口
- [x] P0 移动端完整导航与安全区
- [x] P1 交易表单未保存离开保护
- [x] P1 系统运行状态
- [x] P1 可访问性基础修复
- [x] P1 Playwright 冒烟
- [x] 全量与运行态验证
- [ ] 用户确认提交/部署

## File map

- `src/auth/AuthGate.tsx`: 启动探测、Token 解锁、离线重试和认证失效收口。
- `src/services/apiClient.ts`: 401 清理及认证失效订阅接口。
- `src/main.tsx`: 在路由外接入认证门。
- `src/layouts/MainLayout.tsx`: 移动完整导航、语义 `nav/main/h1` 与跳过导航。
- `src/hooks/useUnsavedChanges.ts`: 路由离开和 `beforeunload` 防丢。
- `src/pages/transactions/TransactionForm.tsx`: dirty 生命周期接入。
- `src/services/metricsService.ts`: `/api/metrics` 类型化薄封装。
- `src/pages/settings/SystemStatusTab.tsx`: 运行状态 UI。
- `src/pages/settings/SettingsPage.tsx`: 注册运行状态 Tab。
- `src/pages/settings/BackupRestoreTab.tsx`: 修复不存在的 Metrics 页面提示。
- `src/components/StatCard.tsx`, `src/pages/dashboard/AlertStatCard.tsx`: 键盘可达导航卡。
- `src/pages/transactions/TransactionList.tsx`, `src/pages/customers/CustomerList.tsx`: 高频列表链接和按钮名称。
- `src/styles/global.css`: 跳过导航、安全区与 reduced-motion。
- `tests/**`: 认证、防丢、指标、导航与可访问性契约。
- `playwright.config.ts`, `tests/e2e/ui-foundation.spec.ts`: 独立端口的无真实数据浏览器冒烟。

### Task 1: P0 统一认证解锁入口

**Files:**
- Create: `src/auth/AuthGate.tsx`
- Modify: `src/services/apiClient.ts`
- Modify: `src/main.tsx`
- Modify: `tests/services/apiClient.test.ts`
- Create: `tests/components/AuthGate.test.tsx`

- [x] **Step 1: 写 401 会话失效测试并确认 RED**

在 `apiClient.test.ts` 监听 `subscribeAuthRequired`，预置 session Token 后模拟 401，断言 Token 被清除且监听器调用一次。

Run: `npm test -- --run tests/services/apiClient.test.ts`

Expected: FAIL，提示 `subscribeAuthRequired` 不存在或 Token 未清除。

- [x] **Step 2: 实现最小认证失效事件并确认 GREEN**

在 `apiClient.ts` 导出：

```ts
export function subscribeAuthRequired(listener: () => void): () => void {
  window.addEventListener(AUTH_REQUIRED_EVENT, listener);
  return () => window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
}
```

401 分支先 `clearApiToken()`，再派发事件，最后抛出现有中文 `ApiException`。

- [x] **Step 3: 写 AuthGate 组件测试并确认 RED**

使用 jsdom 与模块 mock 覆盖三态：无 Token 显示“解锁系统”、后端不可达显示“重新检测”、校验成功渲染 children。

Run: `npm test -- --run tests/components/AuthGate.test.tsx`

Expected: FAIL，`AuthGate` 模块不存在。

- [x] **Step 4: 实现 AuthGate 并接入 Root**

组件只维护 `checking | locked | offline | authenticated`；表单提交调用 `verifyToken`，成功后 `setApiToken` 并进入应用。`main.tsx` 使用：

```tsx
<AuthGate>
  <RouterProvider router={router} />
</AuthGate>
```

- [x] **Step 5: 聚焦验证并更新 Progress**

Run: `npm test -- --run tests/services/apiClient.test.ts tests/components/AuthGate.test.tsx`

Expected: 两个文件全部通过。

### Task 2: P0 移动端完整导航与安全区

**Files:**
- Modify: `src/layouts/MainLayout.tsx`
- Modify: `src/styles/global.css`
- Modify: `tests/utils/layoutNavigation.test.ts`

- [x] **Step 1: 写完整导航契约测试并确认 RED**

导出菜单 key 纯数据或 helper，断言移动全导航覆盖桌面全部 10 个一级路由，且选择后返回目标 key。

Run: `npm test -- --run tests/utils/layoutNavigation.test.ts`

Expected: FAIL，移动全导航数据尚未导出或缺少二级页面。

- [x] **Step 2: 增加移动页头导航 Drawer**

移动页头增加 `MenuOutlined` 的“打开全部导航”按钮；Drawer 中复用完整 `menuItems`，点击后关闭并 `navigate(key)`。桌面侧栏与现有底栏保持不变。

- [x] **Step 3: 增加安全区与触控样式**

底栏高度和页面底部 padding 使用 `env(safe-area-inset-bottom)`；Drawer 增加 `overscroll-behavior: contain`。

- [ ] **Step 4: 聚焦验证并更新 Progress**

Run: `npm test -- --run tests/utils/layoutNavigation.test.ts`

Expected: 全部通过。

### Task 3: P1 交易表单未保存离开保护

**Files:**
- Create: `src/hooks/useUnsavedChanges.ts`
- Modify: `src/pages/transactions/TransactionForm.tsx`
- Create: `tests/utils/unsavedChanges.test.ts`

- [x] **Step 1: 写防丢判定纯函数测试并确认 RED**

定义期望接口 `shouldBlockNavigation({ dirty, submitting, allowNavigation })`，覆盖仅 dirty 且非提交/已放行时返回 true。

Run: `npm test -- --run tests/utils/unsavedChanges.test.ts`

Expected: FAIL，hook 模块不存在。

- [x] **Step 2: 实现 hook 与路由确认**

hook 使用 `useBlocker` 和 `beforeunload`；被阻止时用 `Modal.confirm` 提供“继续编辑/放弃修改”。确认放弃调用 `blocker.proceed()`，取消调用 `blocker.reset()`。

- [x] **Step 3: 接入交易表单 dirty 生命周期**

`Form` 的 `onValuesChange`、新客户昵称和模板选择标记 dirty；提交成功前设置 allowNavigation；保存并继续成功后重置 dirty；接口失败不解除。

- [x] **Step 4: 聚焦验证并更新 Progress**

Run: `npm test -- --run tests/utils/unsavedChanges.test.ts`

Expected: 全部通过且 `npm run check` 无类型错误。

### Task 4: P1 系统运行状态

**Files:**
- Create: `src/services/metricsService.ts`
- Create: `tests/services/metricsService.test.ts`
- Create: `src/pages/settings/SystemStatusTab.tsx`
- Modify: `src/pages/settings/SettingsPage.tsx`
- Modify: `src/pages/settings/BackupRestoreTab.tsx`

- [x] **Step 1: 写 metrics 服务测试并确认 RED**

mock `apiClient.get`，断言 `getMetrics()` 请求 `/api/metrics` 并原样返回账号、同步、备份、通知和 scheduler 字段。

Run: `npm test -- --run tests/services/metricsService.test.ts`

Expected: FAIL，服务模块不存在。

- [x] **Step 2: 实现类型化服务并确认 GREEN**

定义与后端 schema 一致的 `MetricsResponse`，只导出 `getMetrics(): Promise<MetricsResponse>`。

- [x] **Step 3: 实现运行状态 Tab**

首次挂载加载；成功展示状态卡和描述列表，`last_error` 仅作为错误摘要；失败显示 `Result` 与“重新加载”。日期复用 `formatDateTime`。

- [x] **Step 4: 注册真实入口并修复断链**

设置页新增 `system-status` Tab；备份空状态改成“可在「运行状态」查看最近备份时间”。

- [x] **Step 5: 聚焦验证并更新 Progress**

Run: `npm test -- --run tests/services/metricsService.test.ts`

Expected: 全部通过。

### Task 5: P1 可访问性基础修复

**Files:**
- Modify: `src/layouts/MainLayout.tsx`
- Modify: `src/components/StatCard.tsx`
- Modify: `src/pages/dashboard/AlertStatCard.tsx`
- Modify: `src/pages/Dashboard.tsx`
- Modify: `src/pages/transactions/TransactionList.tsx`
- Modify: `src/pages/customers/CustomerList.tsx`
- Modify: `src/styles/global.css`
- Create: `tests/utils/accessibilityBoundary.test.ts`

- [x] **Step 1: 写源码边界测试并确认 RED**

读取上述文件，断言布局存在 skip link、`nav`、`main-content`、`h1`，高频列表按钮出现明确 `aria-label`，统计卡接收真实 `to` 链接而不是裸 `onClick` 导航。

Run: `npm test -- --run tests/utils/accessibilityBoundary.test.ts`

Expected: FAIL，当前布局和列表缺少相应语义。

- [x] **Step 2: 修复布局语义与动画**

增加 skip link、两个 `nav aria-label`、`Content id="main-content" tabIndex={-1}` 和全局页标题 `h1`；CSS 增加可见 focus 和 `prefers-reduced-motion` 降级。

- [x] **Step 3: 修复高频交互语义**

交易/客户名称使用 `Link`；纯图标按钮逐一补动作相关 `aria-label`；统计卡/告警卡以 `to` 生成 `Link` 包裹，不再依赖不可键盘访问的 Card click。

- [x] **Step 4: 聚焦验证并更新 Progress**

Run: `npm test -- --run tests/utils/accessibilityBoundary.test.ts tests/utils/layoutNavigation.test.ts`

Expected: 全部通过。

### Task 6: P1 Playwright 无真实数据冒烟

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `playwright.config.ts`
- Create: `tests/e2e/ui-foundation.spec.ts`

- [x] **Step 1: 安装固定版本 Playwright Test**

Run: `npm install --save-dev @playwright/test@1.55.0`

Expected: package 与 lock 仅增加测试依赖；若网络或浏览器安装需要额外权限，记录为最后确认项，不绕过。

- [x] **Step 2: 写 E2E 测试并确认 RED**

配置 Vite 使用 15174；测试拦截 `/api/auth/*` 与业务 API，断言解锁页、成功进入首页、390px 视口能打开完整导航、页面存在 skip/nav/main/h1。

Run: `npm run test:e2e`

Expected: 首次至少有一项因实现尚未接通或 Chromium 未安装而失败；若是浏览器缺失，只执行官方 install 命令，不改测试规避。

- [x] **Step 3: 使冒烟测试 GREEN**

修正最小选择器/实现连接问题，不调用真实后端、不把 Token 写入日志。

- [x] **Step 4: 更新 Progress**

Run: `npm run test:e2e`

Expected: 全部通过。

### Task 7: 全量验证与确认项收尾

**Files:**
- Modify: `docs/superpowers/plans/2026-07-15-ui-foundation-closure.md`
- Modify: `E:\Obsidian\Codex\projects\XianyuGou.md`

- [x] **Step 1: 前端全量验证**

Run: `npm run check`

Run: `npm test -- --run`

Run: `npm run build`

Expected: 全部退出码 0；build 产物仅为忽略的 `dist`。

- [x] **Step 2: 运行态只读验收**

检查 Docker healthy；使用临时无痕浏览器验证解锁、移动全导航、系统状态与语义结构，不输出 Token 或业务数据。

- [x] **Step 3: 审查差异与既有脏工作区**

Run: `git diff --check`

Run: `git status --short`

Expected: 本轮文件可追溯到计划，原有未提交改动仍保留，无敏感文件出现。

- [x] **Step 4: 更新项目记忆与最终进度**

记录实际完成项、验证结果和剩余阻塞；不记录凭证或真实业务数据。

- [x] **Step 5: 将确认项留给用户**

仅列出是否提交、是否部署、是否清理构建产物等需要授权的动作；用户未确认前不执行。
