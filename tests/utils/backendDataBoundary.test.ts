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
