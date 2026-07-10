import { describe, expect, it } from 'vitest';
import { canManageWarranty, getEnabledWarrantyDays, getWarrantyDaysLabel, getWarrantyFormDefaults, getWarrantyStartLabel } from '@/utils/warranty';
import type { Transaction } from '@/types';

const transaction = (overrides: Partial<Transaction>): Transaction => ({
  id: 1,
  customer_id: 1,
  product_name: '商品A',
  sale_price: 100,
  cost_price: 20,
  profit: 80,
  trade_at: new Date('2026-07-01T10:00:00'),
  status: 'completed',
  warranty_days: 30,
  warranty_end: new Date('2026-08-01T10:00:00'),
  source_type: 'direct',
  attachments: [],
  version: 1,
  created_at: new Date('2026-07-01T10:00:00'),
  updated_at: new Date('2026-07-01T10:00:00'),
  ...overrides,
});

describe('warranty utils', () => {
  it('只有已完成且有质保到期时间的订单允许维护质保', () => {
    expect(canManageWarranty(transaction({}))).toBe(true);
    expect(canManageWarranty(transaction({ warranty_days: 0, warranty_end: undefined }))).toBe(false);
    expect(canManageWarranty(transaction({ status: 'pending', warranty_end: undefined }))).toBe(false);
    expect(canManageWarranty(transaction({ status: 'aftersales' }))).toBe(false);
  });

  it('根据质保和发货状态生成起算时间展示文案', () => {
    const format = (date: Date) => date.toISOString();

    expect(getWarrantyStartLabel(transaction({ warranty_days: 0, warranty_end: undefined }), format)).toBe('不质保');
    expect(getWarrantyStartLabel(transaction({ shipped_at: undefined }), format)).toBe('发货后起算');
    expect(getWarrantyStartLabel(transaction({ shipped_at: new Date('2026-07-02T10:00:00Z') }), format)).toBe('2026-07-02T10:00:00.000Z');
  });

  it('把 0 天质保显示为不质保', () => {
    expect(getWarrantyDaysLabel(0)).toBe('不质保');
    expect(getWarrantyDaysLabel(30)).toBe('30 天');
  });

  it('根据默认质保天数生成交易表单质保默认值', () => {
    expect(getWarrantyFormDefaults(0)).toEqual({ hasWarranty: false, warrantyDays: 0 });
    expect(getWarrantyFormDefaults(30)).toEqual({ hasWarranty: true, warrantyDays: 30 });
  });

  it('开启质保时保证使用正数天数', () => {
    expect(getEnabledWarrantyDays(15, 30)).toBe(15);
    expect(getEnabledWarrantyDays(0, 30)).toBe(30);
    expect(getEnabledWarrantyDays(0, 0)).toBe(30);
  });
});
