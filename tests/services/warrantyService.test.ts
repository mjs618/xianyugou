import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  getUrgentTransactions,
  getWarrantyActiveTransactions,
  getExpiredTransactions,
  getAllWarrantyTransactions,
  extendWarranty,
  endWarrantyEarly,
  getWarrantyExtensions,
} from '@/services/warrantyService';

const TX = (over: any = {}) => ({
  id: 1, customer_id: 5, xianyu_order_no: null, product_name: '商品A',
  sale_price: 100, cost_price: 20, profit: 80, trade_at: '2026-06-01T10:00:00',
  status: 'completed', warranty_end: '2026-07-01T10:00:00', warranty_days: 30,
  source_type: 'direct', source_customer_id: null, notes: null, attachments: [],
  version: 0, created_at: '2026-06-01', updated_at: '2026-06-01', ...over,
});

describe('warrantyService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('getWarrantyActiveTransactions 应 GET /api/warranty/active 并转换日期', async () => {
    setMockResponse('get', '/api/warranty/active', [TX()]);
    const list = await getWarrantyActiveTransactions();
    expect(list.length).toBe(1);
    expect(list[0].trade_at).toBeInstanceOf(Date);
    expect(list[0].warranty_end).toBeInstanceOf(Date);
  });

  it('getUrgentTransactions 应 GET /api/warranty/urgent', async () => {
    setMockResponse('get', '/api/warranty/urgent', [TX({ id: 2 })]);
    const list = await getUrgentTransactions();
    expect(list[0].id).toBe(2);
  });

  it('getExpiredTransactions 应 GET /api/warranty/expired', async () => {
    setMockResponse('get', '/api/warranty/expired', [TX({ id: 3 })]);
    expect((await getExpiredTransactions())[0].id).toBe(3);
  });

  it('getAllWarrantyTransactions 应 GET /api/warranty/all', async () => {
    setMockResponse('get', '/api/warranty/all', [TX(), TX({ id: 2 })]);
    expect((await getAllWarrantyTransactions()).length).toBe(2);
  });

  it('extendWarranty 应 POST /extend 并传递 days/reason', async () => {
    setMockResponse('post', '/api/warranty/1/extend', TX({ warranty_days: 45 }));
    await extendWarranty(1, 15, '客户续费');
    const body = getMockCalls('post', '/api/warranty/1/extend')[0].body as any;
    expect(body).toMatchObject({ days: 15, reason: '客户续费' });
  });

  it('endWarrantyEarly 应 POST /end-early', async () => {
    setMockResponse('post', '/api/warranty/1/end-early', TX());
    await endWarrantyEarly(1, '违规');
    expect(getMockCalls('post', '/api/warranty/1/end-early').length).toBe(1);
  });

  it('getWarrantyExtensions 应 GET extensions 并转换日期', async () => {
    setMockResponse('get', '/api/warranty/1/extensions', [
      { id: 1, transaction_id: 1, old_end: '2026-07-01T10:00:00', new_end: '2026-07-16T10:00:00',
        extended_days: 15, reason: '续费', created_at: '2026-06-20T00:00:00' },
    ]);
    const list = await getWarrantyExtensions(1);
    expect(list[0].extended_days).toBe(15);
    expect(list[0].old_end).toBeInstanceOf(Date);
    expect(list[0].new_end).toBeInstanceOf(Date);
    expect(list[0].created_at).toBeInstanceOf(Date);
  });
});
