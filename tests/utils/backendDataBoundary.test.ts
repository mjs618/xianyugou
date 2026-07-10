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
});
