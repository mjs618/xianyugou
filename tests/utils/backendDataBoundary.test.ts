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

  it('设置页不再暴露本地数据库迁移和浏览器端字段加密状态', () => {
    const source = readFileSync(resolve('src/pages/Settings.tsx'), 'utf8');

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
