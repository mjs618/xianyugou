import { describe, expect, it } from 'vitest';
import { getNavigationBadgeCount } from '@/utils/navigationBadges';

const summary = {
  warrantyUrgent: 2,
  afterSalesPending: 3,
  rebatePending: 4,
};

describe('navigationBadges', () => {
  it('返回质保/售后/财务菜单对应待办数量', () => {
    expect(getNavigationBadgeCount('/warranty', summary)).toBe(2);
    expect(getNavigationBadgeCount('/after-sales', summary)).toBe(3);
    expect(getNavigationBadgeCount('/finance', summary)).toBe(4);
  });

  it('没有待办或不相关菜单返回 0', () => {
    expect(getNavigationBadgeCount('/transactions', summary)).toBe(0);
    expect(getNavigationBadgeCount('/warranty', { ...summary, warrantyUrgent: 0 })).toBe(0);
  });
});
