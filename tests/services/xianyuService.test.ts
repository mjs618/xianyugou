import { beforeEach, describe, expect, it } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { listOrders } from '@/services/xianyuService';

describe('xianyuService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('listOrders 应请求镜像订单并丢弃 raw_order 字段', async () => {
    setMockResponse(
      'get',
      '/api/xianyu/accounts/1/orders',
      [
        {
          id: 10,
          account_id: 1,
          order_no: 'ORDER-1',
          order_status: 'TRADE_FINISHED',
          buyer_nick: 'buyer-a',
          product_name: 'product-a',
          sale_price: 88,
          trade_at: '2026-07-01T12:34:56',
          projected_transaction_id: null,
          last_seen_at: '2026-07-02T12:00:00',
          created_at: '2026-07-01T12:00:00',
          updated_at: '2026-07-02T12:00:00',
          raw_order: { sensitive: 'COOKIE_SENTINEL' },
        },
      ],
      { limit: 50 },
    );

    const orders = await listOrders(1, 50);

    expect(getMockCalls('get', '/api/xianyu/accounts/1/orders')[0].params).toEqual({ limit: 50 });
    expect(orders[0].trade_at).toBeInstanceOf(Date);
    expect(orders[0].last_seen_at).toBeInstanceOf(Date);
    expect(orders[0]).not.toHaveProperty('raw_order');
    expect(JSON.stringify(orders)).not.toContain('COOKIE_SENTINEL');
  });
});
