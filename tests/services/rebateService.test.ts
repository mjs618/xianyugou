import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, setMockError, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  listRebates,
  listByReferrer,
  getPendingCount,
  getPendingTotal,
  getTotalPaid,
  markPaid,
  cancelRebate,
  batchPay,
  getRebateByTransaction,
  updateStatus,
  validateRebateTransition,
} from '@/services/rebateService';

const REBATE = (over: any = {}) => ({
  id: 1, referrer_id: 2, buyer_id: 3, transaction_id: 10,
  amount: 10, rate: 0.1, status: 'pending', paid_at: null, notes: null,
  created_at: '2026-06-01T00:00:00', ...over,
});

describe('rebateService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('validateRebateTransition 状态机（纯函数）', () => {
    expect(() => validateRebateTransition('pending', 'paid')).not.toThrow();
    expect(() => validateRebateTransition('pending', 'cancelled')).not.toThrow();
    expect(() => validateRebateTransition('paid', 'cancelled')).not.toThrow();
    expect(() => validateRebateTransition('cancelled', 'paid')).toThrow();
    expect(() => validateRebateTransition('pending', 'pending')).not.toThrow(); // 同状态无变化
  });

  it('listRebates 应 GET 并转换日期', async () => {
    setMockResponse('get', '/api/rebates', [REBATE()]);
    const list = await listRebates();
    expect(list.length).toBe(1);
    expect(list[0].created_at).toBeInstanceOf(Date);
  });

  it('listByReferrer 应按介绍人查询', async () => {
    setMockResponse('get', '/api/rebates/by-referrer/2', [REBATE()]);
    const list = await listByReferrer(2);
    expect(list.length).toBe(1);
  });

  it('getPendingCount / getPendingTotal 应取对应端点', async () => {
    setMockResponse('get', '/api/rebates/pending-count', { count: 5 });
    setMockResponse('get', '/api/rebates/pending-total', { total: 50.5 });
    expect(await getPendingCount()).toBe(5);
    expect(await getPendingTotal()).toBe(50.5);
  });

  it('getTotalPaid 应从列表聚合已支付金额', async () => {
    setMockResponse('get', '/api/rebates', [
      REBATE({ id: 1, status: 'paid', amount: 30 }),
      REBATE({ id: 2, status: 'paid', amount: 20 }),
      REBATE({ id: 3, status: 'pending', amount: 10 }),
    ]);
    expect(await getTotalPaid()).toBe(50);
  });

  it('markPaid 应 PATCH 状态为 paid', async () => {
    setMockResponse('patch', '/api/rebates/1', REBATE({ status: 'paid' }));
    await markPaid(1, '已转账');
    const body = getMockCalls('patch', '/api/rebates/1')[0].body as any;
    expect(body.status).toBe('paid');
    expect(body.notes).toBe('已转账');
  });

  it('cancelRebate 应 PATCH 状态为 cancelled', async () => {
    setMockResponse('patch', '/api/rebates/1', REBATE({ status: 'cancelled' }));
    await cancelRebate(1);
    expect((getMockCalls('patch', '/api/rebates/1')[0].body as any).status).toBe('cancelled');
  });

  it('markPaid 后端 400 应抛友好错误', async () => {
    setMockError('patch', '/api/rebates/1', 400, '非法状态');
    await expect(markPaid(1)).rejects.toThrow('不存在或状态非法');
  });

  it('batchPay 应 POST /batch-pay', async () => {
    setMockResponse('post', '/api/rebates/batch-pay', { updated: 2, skipped: 1 });
    const r = await batchPay([1, 2, 3]);
    expect(r.updated).toBe(2);
    expect(getMockCalls('post', '/api/rebates/batch-pay')[0].body).toEqual({ ids: [1, 2, 3] });
  });

  it('getRebateByTransaction 有记录返回，无记录返回 undefined', async () => {
    setMockResponse('get', '/api/rebates/by-transaction/10', REBATE());
    expect((await getRebateByTransaction(10))?.id).toBe(1);
    setMockResponse('get', '/api/rebates/by-transaction/11', null);
    expect(await getRebateByTransaction(11)).toBeUndefined();
  });

  it('updateStatus 应 PATCH', async () => {
    setMockResponse('patch', '/api/rebates/1', REBATE({ status: 'paid' }));
    await updateStatus(1, 'paid', '备注');
    const body = getMockCalls('patch', '/api/rebates/1')[0].body as any;
    expect(body.status).toBe('paid');
  });
});
