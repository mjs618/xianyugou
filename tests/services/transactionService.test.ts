import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, setMockError, getMockCalls } from '../mockApiClient';

// mock apiClient —— 必须在 import service 之前；mockApiFactory 经 vi.hoisted 提升可安全引用
vi.mock('@/services/apiClient', () => mockApiFactory());
import { createTransaction, calcProfit, changeStatus, listTransactions, updateTransaction, softDeleteTransaction, getTransaction } from '@/services/transactionService';

describe('transactionService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('应正确计算利润（BR-1）纯函数', () => {
    expect(calcProfit(100, 30)).toBe(70);
    expect(calcProfit(50, 50)).toBe(0);
    expect(calcProfit(30, 50)).toBe(-20);
  });

  it('createTransaction 应 POST /api/transactions 并返回归一化数据', async () => {
    // 后端返回 ISO 字符串，service 应转成 Date
    setMockResponse('post', '/api/transactions', {
      id: 1, customer_id: 5, product_name: '软件激活码',
      sale_price: 128, cost_price: 30, profit: 98,
      trade_at: '2026-06-01T10:00:00', status: 'completed',
      warranty_end: '2026-07-01T10:00:00', warranty_days: 30,
      source_type: 'direct', attachments: [], version: 0,
      created_at: '2026-06-01T10:00:00', updated_at: '2026-06-01T10:00:00',
    });
    const t = await createTransaction({
      customer_id: 5, product_name: '软件激活码',
      sale_price: 128, cost_price: 30, trade_at: new Date('2026-06-01'),
      status: 'completed', warranty_days: 30, source_type: 'direct',
    });
    expect(t.id).toBe(1);
    expect(t.profit).toBe(98);
    expect(t.warranty_end).toBeInstanceOf(Date); // ISO → Date 转换
    expect(t.trade_at).toBeInstanceOf(Date);
    // 验证请求体正确传递
    const calls = getMockCalls('post', '/api/transactions');
    expect(calls[0].body).toMatchObject({ customer_id: 5, product_name: '软件激活码' });
  });

  it('listTransactions 应 GET 并转换日期', async () => {
    setMockResponse('get', '/api/transactions', [
      { id: 1, customer_id: 1, product_name: 'A', sale_price: 100, cost_price: 0, profit: 100,
        trade_at: '2026-06-01', status: 'completed', warranty_days: 30, source_type: 'direct',
        attachments: [], version: 0, created_at: '2026-06-01', updated_at: '2026-06-01', customer_name: '买家' },
    ]);
    const list = await listTransactions();
    expect(list.length).toBe(1);
    expect(list[0].trade_at).toBeInstanceOf(Date);
    expect((list[0] as any).customer_name).toBe('买家'); // 内联客户名透传
  });

  it('changeStatus 应 POST /status 并处理 409 冲突', async () => {
    setMockResponse('post', '/api/transactions/1/status', { id: 1, status: 'completed' });
    await changeStatus(1, 'completed');
    const calls = getMockCalls('post', '/api/transactions/1/status');
    expect(calls[0].body).toMatchObject({ status: 'completed' });

    // 409 冲突应抛出友好错误
    setMockError('post', '/api/transactions/1/status', 409, '冲突');
    await expect(changeStatus(1, 'completed')).rejects.toThrow('已被其他操作修改');
  });

  it('updateTransaction 应 PATCH 并携带 expected_version', async () => {
    setMockResponse('patch', '/api/transactions/1', { id: 1, status: 'completed' });
    await updateTransaction(1, { sale_price: 200, version: 3 } as any);
    const calls = getMockCalls('patch', '/api/transactions/1');
    expect(calls[0].body).toMatchObject({ sale_price: 200, expected_version: 3 });
    expect((calls[0].body as any).version).toBeUndefined(); // version 不应透传给后端
  });

  it('getTransaction 404 应返回 undefined', async () => {
    setMockError('get', '/api/transactions/999', 404, '不存在');
    const t = await getTransaction(999);
    expect(t).toBeUndefined();
  });

  it('softDeleteTransaction 应 DELETE', async () => {
    setMockResponse('delete', '/api/transactions/1', { message: '已删除' });
    await softDeleteTransaction(1);
    expect(getMockCalls('delete', '/api/transactions/1').length).toBe(1);
  });
});
