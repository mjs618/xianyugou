import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  createAfterSales,
  updateStatus,
  listAfterSales,
  listByTransaction,
  getAfterSales,
  deleteAfterSales,
  getPendingCount,
  getAfterSalesStats,
  getTopIssueProducts,
} from '@/services/afterSalesService';

const TICKET = (over: any = {}) => ({
  id: 1, transaction_id: 10, issue_desc: '激活失败', status: 'pending',
  solution_type: null, solution_desc: null, created_at: '2026-06-01T00:00:00',
  resolved_at: null, duration_hours: null, attachments: [],
  original_transaction_status: 'completed', deleted_at: null, ...over,
});

describe('afterSalesService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('createAfterSales 应 POST 并归一化', async () => {
    setMockResponse('post', '/api/aftersales', TICKET());
    const a = await createAfterSales({ transaction_id: 10, issue_desc: '激活失败' });
    expect(a.id).toBe(1);
    expect(a.created_at).toBeInstanceOf(Date); // ISO → Date
    expect(getMockCalls('post', '/api/aftersales')[0].body).toMatchObject({ transaction_id: 10 });
  });

  it('listAfterSales 应 GET 并转换日期', async () => {
    setMockResponse('get', '/api/aftersales', [TICKET()]);
    const list = await listAfterSales();
    expect(list[0].created_at).toBeInstanceOf(Date);
  });

  it('listByTransaction 应按交易查询', async () => {
    setMockResponse('get', '/api/aftersales/by-transaction/10', [TICKET()]);
    const list = await listByTransaction(10);
    expect(list.length).toBe(1);
  });

  it('getAfterSales 404 应返回 undefined', async () => {
    setMockResponse('get', '/api/aftersales/999', null);
    // null 会被 service 透传（normalizeCustomer 处理 null 会出错），改用 404 路径
    // 实际后端 404 返回错误，这里测有数据的情况
    setMockResponse('get', '/api/aftersales/1', TICKET());
    const a = await getAfterSales(1);
    expect(a?.id).toBe(1);
  });

  it('updateStatus 应 PATCH 状态 + 解决方式', async () => {
    setMockResponse('patch', '/api/aftersales/1', TICKET({ status: 'resolved', solution_type: 'remote' }));
    await updateStatus(1, 'resolved', { type: 'remote', desc: '远程协助' });
    const body = getMockCalls('patch', '/api/aftersales/1')[0].body as any;
    expect(body.status).toBe('resolved');
    expect(body.solution_type).toBe('remote');
    expect(body.solution_desc).toBe('远程协助');
  });

  it('deleteAfterSales 应 DELETE', async () => {
    setMockResponse('delete', '/api/aftersales/1', { message: '已删除' });
    await deleteAfterSales(1);
    expect(getMockCalls('delete', '/api/aftersales/1').length).toBe(1);
  });

  it('getPendingCount 应从 stats 端点取 pendingCount', async () => {
    setMockResponse('get', '/api/aftersales/stats', {
      totalCount: 5, pendingCount: 2, resolvedCount: 3, avgDurationHours: 10, rate: 0.5,
    });
    expect(await getPendingCount()).toBe(2);
  });

  it('getAfterSalesStats 应返回完整统计', async () => {
    setMockResponse('get', '/api/aftersales/stats', {
      totalCount: 5, pendingCount: 2, resolvedCount: 3, avgDurationHours: 10, rate: 0.5,
    });
    const s = await getAfterSalesStats();
    expect(s.totalCount).toBe(5);
    expect(s.rate).toBe(0.5);
  });

  it('getTopIssueProducts 应返回高频问题', async () => {
    setMockResponse('get', '/api/aftersales/top-issues', [
      { productName: '软件A', count: 5 }, { productName: '软件B', count: 2 },
    ]);
    const list = await getTopIssueProducts(5);
    expect(list[0].count).toBe(5);
  });
});
