# Stage 2A Page Data Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all page-level IndexedDB business reads and obsolete local-to-backend migration UI while preserving current page behavior through existing backend services.

**Architecture:** Pages compose data returned by service APIs only. Backend export/import remains the supported backup path, but the obsolete bidirectional IndexedDB migration tab and browser-key security claims are removed. Attachment binary storage remains the only intentional Dexie consumer and is handled by the separate Stage 2B plan.

**Tech Stack:** React 18, TypeScript, existing API services, Vitest static boundary regression tests, Vite.

---

## File map

- Create `tests/utils/backendDataBoundary.test.ts`: enforce that application pages and startup do not import the business Dexie database or legacy migration shims.
- Modify `src/pages/customers/CustomerList.tsx`: derive after-sales and referrer filters from backend service results.
- Modify `src/pages/customers/CustomerDetail.tsx`: filter backend after-sales results by the customer's transactions.
- Modify `src/pages/WarrantyBoard.tsx`: resolve customer names from `listCustomers()`.
- Modify `src/pages/Dashboard.tsx`: remove unused Dexie import.
- Modify `src/pages/Settings.tsx`: remove IndexedDB settings inspection, obsolete migration tab, and browser-key security text.
- Modify `src/main.tsx`: remove startup calls to no-op local migration/cleanup functions.
- Modify `src/services/mailRecordService.ts`, `settingsService.ts`, `referralService.ts`, `customerService.ts`, and `trashService.ts`: remove unused legacy compatibility no-ops.
- Modify `tests/services/settingsService.test.ts` and `referralService.test.ts`: stop testing deleted no-op APIs.

### Task 1: Replace page-level Dexie reads

**Files:**
- Create: `tests/utils/backendDataBoundary.test.ts`
- Modify: `src/pages/customers/CustomerList.tsx`
- Modify: `src/pages/customers/CustomerDetail.tsx`
- Modify: `src/pages/WarrantyBoard.tsx`
- Modify: `src/pages/Dashboard.tsx`

- [ ] **Step 1: Write the failing boundary test**

```typescript
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const pageFiles = [
  'src/pages/Dashboard.tsx',
  'src/pages/WarrantyBoard.tsx',
  'src/pages/customers/CustomerList.tsx',
  'src/pages/customers/CustomerDetail.tsx',
];

describe('backend-only page data boundary', () => {
  it.each(pageFiles)('%s 不直接导入业务 IndexedDB', (file) => {
    const source = readFileSync(resolve(file), 'utf8');
    expect(source).not.toContain("from '@/db'");
  });
});
```

- [ ] **Step 2: Run and verify RED**

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts
```

Expected: four cases fail because the listed pages still import `@/db`.

- [ ] **Step 3: Replace `CustomerList` joins**

Import `getReferrerRankings` from `referralService` and remove the `db` import. Load `rankings` and reuse the already loaded `trades`:

```typescript
const [list, aftersales, rankings, trades] = await Promise.all([
  listCustomers(),
  listAfterSales(),
  getReferrerRankings(),
  listTransactions(),
]);

const transactionById = new Map(
  trades.filter((trade) => trade.id !== undefined).map((trade) => [trade.id!, trade])
);
const afterSalesCustomerIds = new Set<number>();
aftersales.forEach((ticket) => {
  const transaction = transactionById.get(ticket.transaction_id);
  if (transaction) afterSalesCustomerIds.add(transaction.customer_id);
});
setHasAftersalesIds(afterSalesCustomerIds);
setReferrerIds(new Set(rankings.map((ranking) => ranking.referrerId)));
```

- [ ] **Step 4: Replace `CustomerDetail` after-sales read**

Import `listAfterSales`, remove `db`, load the backend list once, and filter it:

```typescript
const [allAfterSales, tree, rb] = await Promise.all([
  listAfterSales(),
  getReferralTree(c.id!),
  listByReferrer(c.id!),
]);
const transactionIds = new Set(t.map((transaction) => transaction.id));
setAfterSales(
  allAfterSales.filter((ticket) => transactionIds.has(ticket.transaction_id))
);
```

- [ ] **Step 5: Replace `WarrantyBoard` customer read**

Import `listCustomers`, remove `db`, and load transactions and customers concurrently:

```typescript
const [list, customerList] = await Promise.all([
  getAllWarrantyTransactions(),
  listCustomers(),
]);
const customerIds = new Set(list.map((transaction) => transaction.customer_id));
const map = new Map<number, Customer>();
customerList.forEach((customer) => {
  if (customer.id !== undefined && customerIds.has(customer.id)) {
    map.set(customer.id, customer);
  }
});
setCustomers(map);
```

- [ ] **Step 6: Remove the unused `Dashboard` Dexie import**

Delete only:

```typescript
import { db } from '@/db';
```

- [ ] **Step 7: Run the boundary test and TypeScript check**

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts
npm run check
```

Expected: all four boundary cases and the TypeScript check pass. Settings receives its dedicated boundary assertions in Task 2.

- [ ] **Step 8: Commit page query changes**

```powershell
git add -- tests/utils/backendDataBoundary.test.ts src/pages/Dashboard.tsx src/pages/WarrantyBoard.tsx src/pages/customers/CustomerList.tsx src/pages/customers/CustomerDetail.tsx
git commit -m "refactor: route page joins through backend services"
```

### Task 2: Remove the obsolete migration tab and browser-key status

**Files:**
- Modify: `src/pages/Settings.tsx`
- Modify: `tests/utils/backendDataBoundary.test.ts`

- [ ] **Step 1: Extend the failing Settings regression assertions**

```typescript
it('设置页不提供旧 IndexedDB 迁移入口或浏览器密钥状态', () => {
  const source = readFileSync(resolve('src/pages/Settings.tsx'), 'utf8');
  expect(source).not.toContain("key: 'migrate'");
  expect(source).not.toContain('handleMigrateToBackend');
  expect(source).not.toContain('handlePullFromBackend');
  expect(source).not.toContain('db.settings');
  expect(source).not.toContain('Web Crypto API（AES-GCM 256位）加密存储');
});
```

- [ ] **Step 2: Run and verify RED**

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts
```

Expected: Settings boundary assertions fail on the old migration tab and local database inspection.

- [ ] **Step 3: Remove migration-only state and handlers**

Delete `migrateBackendOnline`, `migrating`, `migrateResult`, `checkMigrateBackend`, `handleMigrateToBackend`, `handlePullFromBackend`, and the `activeTab === 'migrate'` effect. Remove `apiClient`, `checkBackend`, `db`, `CloudSyncOutlined`, and migration-only icon imports when unused.

- [ ] **Step 4: Remove the migration tab object**

Delete the entire Tabs item whose key is `migrate`. Keep JSON backup import/export because those functions already call backend `/api/migrate/export` and `/api/migrate/import`.

- [ ] **Step 5: Replace local encryption status**

Remove `smtpEncrypted`, `isEncrypted`, and `db.settings.get(1)`. Replace the security card content with:

```tsx
<Descriptions.Item label="SMTP 授权码">
  <Tag color="green">后端加密存储（AES-256-GCM）</Tag>
</Descriptions.Item>
<Descriptions.Item label="GPT 密码 / 邮箱密码">
  <Tag color="green">后端写入时自动加密</Tag>
</Descriptions.Item>
```

Use this explanation:

```tsx
description="敏感字段由 FastAPI 后端使用 AES-256-GCM 加密后写入 SQLite。主密钥保存在后端 data/secret.key，不进入浏览器或 Git；数据库与匹配密钥必须配套备份。JSON 业务备份可能包含解密后的敏感字段，导出后应妥善保管。"
```

Replace browser cleanup/cross-device key advice with:

```tsx
<li>结构迁移前使用后端备份工具，并同时保管匹配的 data/secret.key</li>
<li>不要把数据库、密钥、Cookie、Token 或业务备份提交到 Git</li>
```

- [ ] **Step 6: Run boundary test, Settings service tests, and check**

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts tests/services/settingsService.test.ts
npm run check
```

Expected: all tests and TypeScript check pass.

- [ ] **Step 7: Commit Settings cleanup**

```powershell
git add -- src/pages/Settings.tsx tests/utils/backendDataBoundary.test.ts
git commit -m "refactor: remove obsolete local migration settings"
```

### Task 3: Remove startup and service compatibility no-ops

**Files:**
- Modify: `src/main.tsx`
- Modify: `src/services/mailRecordService.ts`
- Modify: `src/services/settingsService.ts`
- Modify: `src/services/referralService.ts`
- Modify: `src/services/customerService.ts`
- Modify: `src/services/trashService.ts`
- Modify: `tests/services/settingsService.test.ts`
- Modify: `tests/services/referralService.test.ts`
- Modify: `tests/utils/backendDataBoundary.test.ts`

- [ ] **Step 1: Add failing startup assertions**

```typescript
it('前端启动不调用本地迁移或清理兼容函数', () => {
  const source = readFileSync(resolve('src/main.tsx'), 'utf8');
  expect(source).not.toContain('migrateEncryptMailRecords');
  expect(source).not.toContain('runAllCleanup');
});
```

- [ ] **Step 2: Run and verify RED**

```powershell
npm test -- --run tests/utils/backendDataBoundary.test.ts
```

Expected: startup assertion fails on both legacy calls.

- [ ] **Step 3: Remove startup imports and calls**

Delete both imports, the migration/cleanup comment, and these calls from `main.tsx`:

```typescript
migrateEncryptMailRecords().catch(() => {});
runAllCleanup().catch(() => {});
```

- [ ] **Step 4: Remove unused compatibility exports**

Delete these unreferenced functions and their compatibility comments:

- `migrateEncryptMailRecords` from `mailRecordService.ts`
- `migrateEncryptSettings` from `settingsService.ts`
- `createReferralAndRebate` from `referralService.ts`
- `recalcAllCustomersStats` from `customerService.ts`
- `cleanupExpiredSoftDeletes`, `cleanupOldLogs`, `cleanupOldNotifications`, and `runAllCleanup` from `trashService.ts`

Remove the corresponding no-op tests and imports from `settingsService.test.ts` and `referralService.test.ts`.

- [ ] **Step 5: Verify no compatibility symbol remains**

```powershell
rg -n "migrateEncryptMailRecords|migrateEncryptSettings|createReferralAndRebate|recalcAllCustomersStats|runAllCleanup" src tests
```

Expected: no matches.

- [ ] **Step 6: Run full frontend verification**

```powershell
npm test -- --run
npm run check
npm run build
git diff --check
```

Expected: all tests pass, TypeScript check passes, production build exits `0`, and diff check has no output.

- [ ] **Step 7: Commit compatibility cleanup**

```powershell
git add -- src/main.tsx src/services/mailRecordService.ts src/services/settingsService.ts src/services/referralService.ts src/services/customerService.ts src/services/trashService.ts tests/services/settingsService.test.ts tests/services/referralService.test.ts tests/utils/backendDataBoundary.test.ts
git commit -m "refactor: remove frontend data migration shims"
```

### Task 4: Runtime verification

**Files:**
- Verify only.

- [ ] **Step 1: Rebuild the web container**

```powershell
docker compose up -d --build web
```

- [ ] **Step 2: Verify services and HTTP health**

```powershell
docker compose ps
```

Verify HTTP 200 for the web root, backend `/api/health`, and mail `/api/health`.

- [ ] **Step 3: Verify backend database and backup remain valid**

```powershell
docker compose exec backend python -m app.maintenance.database_schema current
docker compose exec backend python -m app.maintenance.database_backup verify --database /app/backups/xianyu-20260710-pre-alembic.db --manifest /app/backups/xianyu-20260710-pre-alembic.manifest.json
```

Expected: `current=head=20260710_02` and backup verification passes.

## Stage 2A completion gate

- No React page imports `@/db` or reads IndexedDB business tables.
- Customer, after-sales, referral, warranty, settings, and dashboard views use backend services only.
- The obsolete local-to-backend migration tab is gone; backend JSON backup/restore remains available.
- Security text accurately describes backend encryption and key custody.
- Frontend startup performs no local migration or no-op cleanup.
- Attachment storage remains the only deliberate Dexie business consumer pending Stage 2B.
- Full frontend tests, type check, build, Docker status, HTTP health, database revision, and backup verification pass.
