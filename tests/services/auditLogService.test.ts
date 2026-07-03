import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { logOperation, listLogs, getLogCount, clearLogs } from '@/services/auditLogService';

const LOG = (over: any = {}) => ({
  id: 1, module: 'transaction', action: 'create', target_id: 1, target_name: '商品A',
  detail: '售价:100', created_at: '2026-06-30T00:00:00', ...over,
});

describe('auditLogService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('logOperation 应为 no-op（后端自动记录）', async () => {
    await expect(logOperation('transaction', 'create', { target_id: 1 })).resolves.toBeUndefined();
  });

  it('listLogs 应 GET /api/operation-logs 并转换日期', async () => {
    setMockResponse('get', '/api/operation-logs', {
      items: [LOG({ id: 1, target_name: 'A' }), LOG({ id: 2, target_name: 'B' })],
      total: 2,
    }, { module: undefined, page: 1, page_size: 100 });
    const logs = await listLogs({ limit: 100 });
    expect(logs.length).toBe(2);
    expect(logs[0].created_at).toBeInstanceOf(Date);
    expect(logs[0].target_name).toBe('A');
  });

  it('listLogs 应传递 module 筛选', async () => {
    setMockResponse('get', '/api/operation-logs', {
      items: [LOG({ module: 'transaction' })], total: 1,
    }, { module: 'transaction', page: 1, page_size: 100 });
    const logs = await listLogs({ module: 'transaction' });
    expect(logs[0].module).toBe('transaction');
    const params = getMockCalls('get', '/api/operation-logs')[0].params as any;
    expect(params.module).toBe('transaction');
  });

  it('getLogCount 应返回 total', async () => {
    setMockResponse('get', '/api/operation-logs', { items: [], total: 5 }, { module: undefined, page: 1, page_size: 1 });
    expect(await getLogCount()).toBe(5);
  });

  it('getLogCount 支持 module 筛选', async () => {
    setMockResponse('get', '/api/operation-logs', { items: [], total: 3 }, { module: 'customer', page: 1, page_size: 1 });
    expect(await getLogCount('customer')).toBe(3);
  });

  it('clearLogs 应 DELETE /api/operation-logs', async () => {
    setMockResponse('delete', '/api/operation-logs', { message: '已清空' });
    await clearLogs();
    expect(getMockCalls('delete', '/api/operation-logs').length).toBe(1);
  });
});
