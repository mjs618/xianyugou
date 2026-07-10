import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { getSettings, updateSettings } from '@/services/settingsService';
import { DEFAULT_SETTINGS } from '@/types';

describe('settingsService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('getSettings 应 GET /api/settings', async () => {
    setMockResponse('get', '/api/settings', { ...DEFAULT_SETTINGS });
    const s = await getSettings();
    expect(s.id).toBe(1);
    expect(s.warranty_days).toBe(DEFAULT_SETTINGS.warranty_days);
    expect(s.rebate_rate).toBe(DEFAULT_SETTINGS.rebate_rate);
    expect(getMockCalls('get', '/api/settings').length).toBe(1);
  });

  it('getSettings 后端不可用时应回退默认设置', async () => {
    // 不设 mock 响应 → mock 抛错 → getSettings 捕获并返回默认值
    const s = await getSettings();
    expect(s.warranty_days).toBe(DEFAULT_SETTINGS.warranty_days);
    expect(s.rebate_rate).toBe(DEFAULT_SETTINGS.rebate_rate);
  });

  it('updateSettings 应 PUT /api/settings 并返回更新值', async () => {
    const updated = { ...DEFAULT_SETTINGS, warranty_days: 60, rebate_rate: 0.15, rebate_base: 'sale' };
    setMockResponse('put', '/api/settings', updated);
    const s = await updateSettings({ warranty_days: 60, rebate_rate: 0.15, rebate_base: 'sale' });
    expect(s.warranty_days).toBe(60);
    expect(s.rebate_rate).toBe(0.15);
    expect(s.rebate_base).toBe('sale');
    // 验证请求体正确传递
    const calls = getMockCalls('put', '/api/settings');
    expect(calls[0].body).toMatchObject({ warranty_days: 60, rebate_rate: 0.15 });
  });

  it('updateSettings 应允许 warranty_days 为 0 表示默认不质保', async () => {
    setMockResponse('put', '/api/settings', { ...DEFAULT_SETTINGS, warranty_days: 0 });
    const s = await updateSettings({ warranty_days: 0 });
    expect(s.warranty_days).toBe(0);
    expect((getMockCalls('put', '/api/settings')[0].body as any).warranty_days).toBe(0);
  });

  it('updateSettings 部分更新应只传指定字段', async () => {
    setMockResponse('put', '/api/settings', { ...DEFAULT_SETTINGS, recall_days: 60 });
    await updateSettings({ recall_days: 60 });
    const body = getMockCalls('put', '/api/settings')[0].body as any;
    expect(body.recall_days).toBe(60);
    expect(body.warranty_days).toBeUndefined(); // 未指定字段不应传递
  });

  it('migrateEncryptSettings 应为 no-op（加密由后端处理）', async () => {
    const { migrateEncryptSettings } = await import('@/services/settingsService');
    await expect(migrateEncryptSettings()).resolves.toBeUndefined();
  });
});
