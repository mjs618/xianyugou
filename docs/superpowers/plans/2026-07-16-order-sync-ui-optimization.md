# Order Sync Task-First UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dense order-sync alerts and fixed-width action table with a task-first, responsive operations console while preserving all existing API and business behavior.

**Architecture:** Keep `OrderSyncPage` as the data and command container. Add one pure summary view-model module, one presentational overview component, and replace the table renderer with a responsive account-card grid whose callbacks remain injected from the container. Styling stays local to the order-sync feature.

**Tech Stack:** React 18, TypeScript, Ant Design 5, Vitest, Testing Library, Playwright, Vite, Docker Compose.

---

## File map

- Create `src/pages/ordersync/orderSyncViewModel.ts`: derive overview counts and paused-account labels from existing account data.
- Create `src/pages/ordersync/OrderSyncOverview.tsx`: summary strip, recovery task, CookieCloud task, and collapsed usage help.
- Create `src/pages/ordersync/AccountCardGrid.tsx`: responsive account cards and state-aware actions.
- Create `src/pages/ordersync/orderSync.css`: feature-local layout and responsive styling.
- Modify `src/pages/ordersync/OrderSyncPage.tsx`: compose the new overview and card grid; keep all API calls and handlers here.
- Delete `src/pages/ordersync/AccountTable.tsx`: replaced by the card grid after its behavior is covered.
- Create `tests/components/orderSyncViewModel.test.ts`: pure summary behavior.
- Create `tests/components/OrderSyncOverview.test.tsx`: overview content and disclosure behavior.
- Create `tests/components/AccountCardGrid.test.tsx`: state-aware primary actions, secondary menu, and empty state.
- Modify `tests/e2e/ui-foundation.spec.ts`: mocked desktop and mobile order-sync smoke coverage.

### Task 1: Derive stable overview data

**Files:**
- Create: `src/pages/ordersync/orderSyncViewModel.ts`
- Test: `tests/components/orderSyncViewModel.test.ts`

- [ ] **Step 1: Write the failing summary tests**

Cover total accounts, attention statuses (`paused`, `invalid`, `risk`), active automatic sync, and paused nicknames:

```ts
import { describe, expect, it } from 'vitest';
import { getOrderSyncOverview } from '@/pages/ordersync/orderSyncViewModel';

it('derives attention and active auto-sync counts', () => {
  const accounts = [
    account({ id: 1, nickname: '正常', status: 'online', auto_sync_enabled: true }),
    account({ id: 2, nickname: '暂停', status: 'paused', auto_sync_enabled: true }),
    account({ id: 3, nickname: '风控', status: 'risk', auto_sync_enabled: false }),
  ];
  expect(getOrderSyncOverview(accounts)).toEqual({
    total: 3,
    needsAttention: 2,
    autoSyncActive: 1,
    pausedNames: ['暂停'],
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run tests/components/orderSyncViewModel.test.ts`

Expected: FAIL because `orderSyncViewModel.ts` does not exist.

- [ ] **Step 3: Implement the minimal pure view model**

```ts
import type { XianyuAccount } from '@/types';

export interface OrderSyncOverviewData {
  total: number;
  needsAttention: number;
  autoSyncActive: number;
  pausedNames: string[];
}

export function getOrderSyncOverview(accounts: XianyuAccount[]): OrderSyncOverviewData {
  const attentionStatuses = new Set(['paused', 'invalid', 'risk']);
  return {
    total: accounts.length,
    needsAttention: accounts.filter((account) => attentionStatuses.has(account.status)).length,
    autoSyncActive: accounts.filter(
      (account) => account.auto_sync_enabled && account.status !== 'paused',
    ).length,
    pausedNames: accounts
      .filter((account) => account.status === 'paused')
      .map((account) => account.nickname),
  };
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- --run tests/components/orderSyncViewModel.test.ts`

Expected: all tests in the file pass.

- [ ] **Step 5: Commit the view model**

```powershell
git add -- src/pages/ordersync/orderSyncViewModel.ts tests/components/orderSyncViewModel.test.ts
git commit -m "test: define order sync overview state"
```

### Task 2: Build the task-first overview

**Files:**
- Create: `src/pages/ordersync/OrderSyncOverview.tsx`
- Create: `src/pages/ordersync/orderSync.css`
- Modify: `src/pages/ordersync/OrderSyncPage.tsx`
- Test: `tests/components/OrderSyncOverview.test.tsx`

- [ ] **Step 1: Write failing overview component tests**

Use jsdom and render the component with three accounts. Assert that it exposes the four summary labels, the paused account recovery path, a disabled CookieCloud task, and a collapsed help trigger:

```tsx
// @vitest-environment jsdom
render(
  <OrderSyncOverview
    accounts={accounts}
    cookieCloudStatus={cookieCloudDisabled}
    onReloadCookieCloud={vi.fn()}
  />,
);
expect(screen.getByText('全部账号')).toBeInTheDocument();
expect(screen.getByText('待处理')).toBeInTheDocument();
expect(screen.getByText('更新 Cookie')).toBeInTheDocument();
expect(screen.getByText('校验')).toBeInTheDocument();
expect(screen.getByText('恢复')).toBeInTheDocument();
expect(screen.getByRole('button', { name: /同步说明与 Cookie 获取方法/ })).toBeInTheDocument();
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run tests/components/OrderSyncOverview.test.tsx`

Expected: FAIL because `OrderSyncOverview` does not exist.

- [ ] **Step 3: Implement the overview with existing data only**

Implement:

```tsx
const summary = getOrderSyncOverview(accounts);

<section aria-label="同步状态总览" className="order-sync-overview">
  <div className="order-sync-summary-grid">
    <SummaryItem label="全部账号" value={summary.total} />
    <SummaryItem label="待处理" value={summary.needsAttention} tone="danger" />
    <SummaryItem label="自动同步" value={summary.autoSyncActive} />
    <SummaryItem
      label="CookieCloud"
      value={cookieCloudStatus === null ? '状态未知' : cookieCloudStatus.enabled ? '已启用' : '未启用'}
      tone={cookieCloudStatus?.enabled ? 'success' : 'warning'}
    />
  </div>
  {summary.pausedNames.length > 0 && <RecoveryTask names={summary.pausedNames} />}
  {cookieCloudStatus && !cookieCloudStatus.enabled && (
    <CookieCloudTask status={cookieCloudStatus} onReload={onReloadCookieCloud} />
  )}
  <Collapse ghost items={[{ key: 'help', label: '同步说明与 Cookie 获取方法', children: <SyncHelp /> }]} />
</section>
```

Keep the existing help wording. Put missing CookieCloud keys in the task detail, not in the task title. Add CSS for a four-column summary that becomes two columns below 900px and one column below 520px.

- [ ] **Step 4: Integrate and remove the three always-expanded alerts**

Import `OrderSyncOverview` and `orderSync.css` in `OrderSyncPage.tsx`. Replace the information Alert, CookieCloud Alert, and paused-account Alert with:

```tsx
<OrderSyncOverview
  accounts={accounts}
  cookieCloudStatus={cookieCloudStatus}
  onReloadCookieCloud={loadCookieCloudStatus}
/>
```

Do not modify the last sync result alerts or any handler.

- [ ] **Step 5: Run focused and existing service tests**

Run: `npm test -- --run tests/components/OrderSyncOverview.test.tsx tests/components/orderSyncViewModel.test.ts tests/services/xianyuService.test.ts`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the overview**

```powershell
git add -- src/pages/ordersync/OrderSyncOverview.tsx src/pages/ordersync/orderSync.css src/pages/ordersync/OrderSyncPage.tsx tests/components/OrderSyncOverview.test.tsx
git commit -m "feat: prioritize order sync health tasks"
```

### Task 3: Replace the fixed action table with responsive account cards

**Files:**
- Create: `src/pages/ordersync/AccountCardGrid.tsx`
- Modify: `src/pages/ordersync/orderSync.css`
- Modify: `src/pages/ordersync/OrderSyncPage.tsx`
- Delete: `src/pages/ordersync/AccountTable.tsx`
- Test: `tests/components/AccountCardGrid.test.tsx`

- [ ] **Step 1: Write failing card-grid tests**

Create paused and online accounts with injected spies. Assert:

```tsx
expect(screen.getByRole('button', { name: '更新 Cookie 0618' })).toBeVisible();
expect(screen.getByRole('button', { name: '校验并恢复 0618' })).toBeVisible();
expect(screen.getByRole('button', { name: '同步订单 正常账号' })).toBeVisible();
expect(screen.getByRole('button', { name: '同步商品 正常账号' })).toBeVisible();

fireEvent.click(screen.getByRole('button', { name: '更多操作 正常账号' }));
expect(await screen.findByRole('menuitem', { name: '订单镜像' })).toBeVisible();
expect(screen.getByRole('menuitem', { name: '商品镜像' })).toBeVisible();
expect(screen.getByRole('menuitem', { name: '同步日志' })).toBeVisible();
```

Add a separate test that `accounts={[]}` renders “还没有闲鱼账号” and calls `onAddAccount` from its button.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run tests/components/AccountCardGrid.test.tsx`

Expected: FAIL because `AccountCardGrid` does not exist.

- [ ] **Step 3: Implement state-aware cards**

Preserve every existing callback prop. Each card must render identity, status, last sync, automatic sync controls, failure count, and last error. Main actions:

```tsx
{isPaused ? (
  <>
    <Button aria-label={`更新 Cookie ${account.nickname}`} onClick={() => onEdit(account)}>
      更新 Cookie
    </Button>
    <Popconfirm title="校验并恢复账号？" onConfirm={() => onRecover(account.id)}>
      <Button aria-label={`校验并恢复 ${account.nickname}`} danger>
        校验并恢复
      </Button>
    </Popconfirm>
  </>
) : (
  <>
    <Button aria-label={`同步订单 ${account.nickname}`} type="primary" onClick={() => onSync(account.id)}>
      同步订单
    </Button>
    <Button aria-label={`同步商品 ${account.nickname}`} onClick={() => onSyncItems(account.id)}>
      同步商品
    </Button>
  </>
)}
```

Use an Ant Design `Dropdown` for secondary actions. Map menu keys to the injected handlers; use `Modal.confirm` before invoking `onDelete`. Keep automatic-sync optimistic editing behavior in the container unchanged.

- [ ] **Step 4: Add responsive feature CSS**

Implement `.order-sync-account-grid` with `repeat(auto-fit, minmax(min(100%, 360px), 1fr))`, card sections with neutral borders, a low-saturation error panel, and a single-column mobile rule. Use existing CSS variables and no new global theme tokens.

- [ ] **Step 5: Integrate the grid and remove the table**

Replace the `AccountTable` import and element with `AccountCardGrid`, pass the existing callbacks, add `onAddAccount` that opens the existing form modal, then delete `AccountTable.tsx`.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `npm test -- --run tests/components/AccountCardGrid.test.tsx tests/components/OrderSyncOverview.test.tsx tests/services/xianyuService.test.ts`

Expected: all selected tests pass.

- [ ] **Step 7: Commit the responsive cards**

```powershell
git add -- src/pages/ordersync/AccountCardGrid.tsx src/pages/ordersync/AccountTable.tsx src/pages/ordersync/orderSync.css src/pages/ordersync/OrderSyncPage.tsx tests/components/AccountCardGrid.test.tsx
git commit -m "feat: add responsive order sync account cards"
```

### Task 4: Add browser coverage and finish deployment

**Files:**
- Modify: `tests/e2e/ui-foundation.spec.ts`
- Modify: `E:\Obsidian\Codex\projects\XianyuGou.md` after verification

- [ ] **Step 1: Extend mocked API responses**

Return deterministic paused and online accounts for `/api/xianyu/accounts`, enabled/disabled configuration for `/api/xianyu/cookiecloud/status`, and `{ ok: true }` for `/api/health`. Do not include a real Cookie or Token.

- [ ] **Step 2: Write the browser assertions**

Add desktop and 390px tests that unlock with the existing fake token, navigate to `/order-sync`, and assert:

```ts
await expect(page.getByRole('region', { name: '同步状态总览' })).toBeVisible();
await expect(page.getByText('3 个账号需要处理')).toBeVisible();
await expect(page.getByRole('button', { name: '更新 Cookie 0618' })).toBeVisible();
await expect(page.getByRole('button', { name: /同步说明与 Cookie 获取方法/ })).toBeVisible();
await expect(page.locator('body')).not.toHaveCSS('overflow-x', 'scroll');
```

- [ ] **Step 3: Run full frontend verification**

Run:

```powershell
npm test -- --run
npm run check
npm run build
npm run test:e2e
```

Expected: all Vitest and Playwright tests pass, TypeScript exits 0, production build exits 0. Existing Vite `use client` and chunk-size warnings may remain.

- [ ] **Step 4: Review the complete diff**

Run:

```powershell
git diff --check
git status --short
git diff --stat HEAD~3
```

Confirm no backend, database, credential, or unrelated files changed.

- [ ] **Step 5: Rebuild the Web container**

Run: `docker compose up -d --build web`

Expected: `xianyugou-web` is recreated and reaches `healthy`; backend and mail remain healthy.

- [ ] **Step 6: Verify the deployed page without mutations**

Use a clean Playwright context against `http://127.0.0.1:15173`, inject the API Token only into session storage without printing it, and verify the desktop and 390px layouts. Do not click sync, recover, edit, or delete.

- [ ] **Step 7: Record project state and push**

Append concise implementation, tests, Docker health, and remaining warning notes to `E:\Obsidian\Codex\projects\XianyuGou.md`. Confirm the repository worktree is clean, then push `codex/safe-order-lifecycle-sync`.
