import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const pageFiles = [
  'src/pages/Dashboard.tsx',
  'src/pages/WarrantyBoard.tsx',
  'src/pages/customers/CustomerList.tsx',
  'src/pages/customers/CustomerDetail.tsx',
  // E2 拆分后把 settings/ 子文件纳入扫描，避免覆盖盲点
  'src/pages/Settings.tsx',
  'src/pages/settings/SettingsPage.tsx',
  'src/pages/settings/ThemeTab.tsx',
  'src/pages/settings/NotificationTab.tsx',
  'src/pages/settings/ApiTokenTab.tsx',
  'src/pages/settings/SecurityStatusTab.tsx',
  // E3 拆分后把 ordersync/ 子文件纳入扫描
  'src/pages/OrderSync.tsx',
];

// 自动收集 src/pages/settings/ 下所有 .tsx 文件（未来新增子组件自动纳入扫描）
const settingsDirFiles = readdirSync(resolve('src/pages/settings'))
  .filter((f) => f.endsWith('.tsx'))
  .map((f) => `src/pages/settings/${f}`);

// 自动收集 src/pages/ordersync/ 下所有 .tsx 文件（E3 拆分后新增）
const ordersyncDirFiles = readdirSync(resolve('src/pages/ordersync'))
  .filter((f) => f.endsWith('.tsx'))
  .map((f) => `src/pages/ordersync/${f}`);

describe('backend-only page data boundary', () => {
  it.each(pageFiles)('%s 不直接导入业务 IndexedDB', (file) => {
    const source = readFileSync(resolve(file), 'utf8');
    expect(source).not.toContain("from '@/db'");
  });

  it('设置页及其拆分子组件不再暴露本地数据库迁移和浏览器端字段加密状态', () => {
    // 拆分后 Settings.tsx 是薄壳，子文件在 src/pages/settings/*.tsx
    // 用 settingsDirFiles 自动收集所有子文件 + 薄壳入口一并扫描
    const settingsFiles = ['src/pages/Settings.tsx', ...settingsDirFiles];
    const source = settingsFiles
      .map((file) => readFileSync(resolve(file), 'utf8'))
      .join('\n');

    expect(source).not.toContain("from '@/db'");
    expect(source).not.toContain('handleMigrateToBackend');
    expect(source).not.toContain("key: 'migrate'");
    expect(source).not.toContain('Web Crypto API');
  });

  it('启动链和服务层不保留已迁移到后端的空操作', () => {
    const files = [
      'src/main.tsx',
      'src/services/customerService.ts',
      'src/services/mailRecordService.ts',
      'src/services/referralService.ts',
      'src/services/settingsService.ts',
      'src/services/trashService.ts',
    ];
    const source = files.map((file) => readFileSync(resolve(file), 'utf8')).join('\n');

    [
      'migrateEncryptMailRecords',
      'migrateEncryptSettings',
      'createReferralAndRebate',
      'recalcAllCustomersStats',
      'runAllCleanup',
    ].forEach((obsoleteName) => expect(source).not.toContain(obsoleteName));
  });

  it('前端生产代码和依赖不再包含业务 IndexedDB', () => {
    const packageJson = readFileSync(resolve('package.json'), 'utf8');
    const attachmentService = readFileSync(
      resolve('src/services/attachmentService.ts'),
      'utf8',
    );
    const setup = readFileSync(resolve('tests/setup.ts'), 'utf8');

    expect(packageJson).not.toContain('"dexie"');
    expect(packageJson).not.toContain('"fake-indexeddb"');
    expect(attachmentService).not.toContain("from '@/db'");
    expect(setup).not.toContain('fake-indexeddb');
  });
});
