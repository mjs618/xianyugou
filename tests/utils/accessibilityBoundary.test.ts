import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

function source(path: string): string {
  return readFileSync(path, 'utf8');
}

describe('UI 可访问性边界', () => {
  it('主布局提供跳转链接、导航地标、主内容和页面标题', () => {
    const layout = source('src/layouts/MainLayout.tsx');
    expect(layout).toContain('href="#main-content"');
    expect(layout).toContain('aria-label="主导航"');
    expect(layout).toContain('aria-label="移动快捷导航"');
    expect(layout).toContain('id="main-content"');
    expect(layout).toContain('<h1');
  });

  it('仪表盘统计卡使用真实路由链接', () => {
    for (const path of ['src/components/StatCard.tsx', 'src/pages/dashboard/AlertStatCard.tsx']) {
      const content = source(path);
      expect(content).toContain("import { Link }");
      expect(content).toMatch(/to\??: string/);
      expect(content).toContain('<Link');
    }
  });

  it('高频列表使用链接并为图标按钮提供可读名称', () => {
    const transactionList = source('src/pages/transactions/TransactionList.tsx');
    const customerList = source('src/pages/customers/CustomerList.tsx');
    expect(transactionList).toContain('<Link');
    expect(transactionList).toContain('aria-label={`查看交易');
    expect(transactionList).toContain('aria-label={`删除交易');
    expect(customerList).toContain('<Link');
    expect(customerList).toContain('aria-label={`查看客户');
    expect(customerList).toContain('aria-label={`删除客户');
  });
});
