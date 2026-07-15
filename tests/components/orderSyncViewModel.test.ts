import { describe, expect, it } from 'vitest';
import { getOrderSyncOverview } from '@/pages/ordersync/orderSyncViewModel';
import type { XianyuAccount } from '@/types';

function account(overrides: Partial<XianyuAccount>): XianyuAccount {
  return {
    id: 1,
    nickname: '测试账号',
    status: 'online',
    auto_sync_enabled: false,
    auto_sync_interval_minutes: 60,
    consecutive_failures: 0,
    created_at: new Date('2026-07-01T00:00:00Z'),
    updated_at: new Date('2026-07-01T00:00:00Z'),
    ...overrides,
  };
}

describe('getOrderSyncOverview', () => {
  it('派生待处理与有效自动同步账号数量', () => {
    const accounts = [
      account({ id: 1, nickname: '正常', status: 'online', auto_sync_enabled: true }),
      account({ id: 2, nickname: '暂停', status: 'paused', auto_sync_enabled: true }),
      account({ id: 3, nickname: '风控', status: 'risk', auto_sync_enabled: false }),
      account({ id: 4, nickname: '失效', status: 'invalid', auto_sync_enabled: false }),
    ];

    expect(getOrderSyncOverview(accounts)).toEqual({
      total: 4,
      needsAttention: 3,
      autoSyncActive: 1,
      pausedNames: ['暂停'],
    });
  });

  it('空账号列表返回全零总览', () => {
    expect(getOrderSyncOverview([])).toEqual({
      total: 0,
      needsAttention: 0,
      autoSyncActive: 0,
      pausedNames: [],
    });
  });
});
