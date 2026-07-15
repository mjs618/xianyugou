import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getMockCalls, mockApiFactory, resetMockApi, setMockResponse } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { getMetrics } from '@/services/metricsService';

describe('metricsService', () => {
  beforeEach(resetMockApi);

  it('读取并原样返回系统运行指标', async () => {
    const metrics = {
      timestamp: '2026-07-15T15:00:00Z',
      accounts: { total: 3, online: 2, paused: 1, invalid: 0 },
      sync: {
        last_24h_success: 8,
        last_24h_failed: 1,
        last_24h_fetched_orders: 20,
        last_24h_created_transactions: 4,
        last_error: 'cookie expired',
        last_sync_at: '2026-07-15T14:30:00Z',
      },
      backup: {
        last_backup_at: '2026-07-15T02:00:00Z',
        backup_count: 7,
        backup_dir_exists: true,
      },
      notifications_unread: 5,
      scheduler_running: true,
    };
    setMockResponse('get', '/api/metrics', metrics);

    await expect(getMetrics()).resolves.toEqual(metrics);
    expect(getMockCalls('get', '/api/metrics')).toHaveLength(1);
  });
});
