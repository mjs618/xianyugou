import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { createExpense, deleteExpense, listExpenses, updateExpense } from '@/services/expenseService';

describe('expenseService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  const row = {
    id: 1,
    category: '擦亮',
    amount: 6,
    occurred_at: '2026-07-09T10:00:00Z',
    notes: '商品擦亮',
    created_at: '2026-07-09T10:00:00Z',
    updated_at: '2026-07-09T10:00:00Z',
  };

  it('listExpenses 应按范围 GET /api/expenses', async () => {
    setMockResponse('get', '/api/expenses', [row]);
    const result = await listExpenses(new Date('2026-07-01'), new Date('2026-07-31'));
    const params = getMockCalls('get', '/api/expenses')[0].params as any;

    expect(params.start).toBeDefined();
    expect(params.end).toBeDefined();
    expect(result[0].occurred_at).toBeInstanceOf(Date);
  });

  it('createExpense 应 POST 支出', async () => {
    setMockResponse('post', '/api/expenses', row);
    await createExpense({ category: '擦亮', amount: 6, occurred_at: new Date('2026-07-09T10:00:00Z') });
    const body = getMockCalls('post', '/api/expenses')[0].body as any;

    expect(body.category).toBe('擦亮');
    expect(body.amount).toBe(6);
    expect(body.occurred_at).toContain('2026-07-09');
  });

  it('updateExpense 应 PATCH 指定支出', async () => {
    setMockResponse('patch', '/api/expenses/1', row);
    await updateExpense(1, { notes: '更新' });

    expect(getMockCalls('patch', '/api/expenses/1')[0].body).toEqual({ notes: '更新' });
  });

  it('deleteExpense 应 DELETE 指定支出', async () => {
    setMockResponse('delete', '/api/expenses/1', { message: '已删除' });
    await deleteExpense(1);

    expect(getMockCalls('delete', '/api/expenses/1')).toHaveLength(1);
  });
});
