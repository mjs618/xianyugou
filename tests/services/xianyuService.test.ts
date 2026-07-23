import { beforeEach, describe, expect, it } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, setMockError, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  filterXianyuOrdersByProjection,
  filterXianyuItemsByTemplateProjection,
  formatXianyuOrderProjectionSummary,
  formatItemSyncResultMessage,
  formatSyncResultMessage,
  getCookieCloudConfigStatus,
  hasSyncedItemsToView,
  hasSyncedOrdersToView,
  importXianyuItemsAsTemplates,
  listItems,
  listOrders,
  recoverAccount,
  summarizeXianyuItems,
  summarizeXianyuOrders,
  syncItems,
  syncOrders,
  updateAccount,
} from '@/services/xianyuService';

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
  it('syncOrders returns a stable message for an account-level sync conflict', async () => {
    setMockError(
      'post',
      '/api/xianyu/accounts/1/sync-orders',
      409,
      'running',
      { max_pages: 10 },
    );

    await expect(syncOrders(1)).rejects.toThrow('该账号订单同步正在进行中，请稍后再试');
  });

  it('getCookieCloudConfigStatus fetches local auto-refresh readiness without secrets', async () => {
    setMockResponse('get', '/api/xianyu/cookiecloud/status', {
      enabled: false,
      missing_keys: ['COOKIE_CLOUD_UUID', 'COOKIE_CLOUD_PASSWORD'],
      domain_keyword: 'goofish.com',
      message: 'CookieCloud 未配置完整，Cookie 过期后不会自动续 Cookie。',
      next_step: '在项目根目录 .env 中补齐 COOKIE_CLOUD_UUID、COOKIE_CLOUD_PASSWORD，或手动更新账号 Cookie。',
    });

    const status = await getCookieCloudConfigStatus();

    expect(status.enabled).toBe(false);
    expect(status.missing_keys).toEqual(['COOKIE_CLOUD_UUID', 'COOKIE_CLOUD_PASSWORD']);
    expect(status.message).toContain('不会自动续 Cookie');
    expect(JSON.stringify(status)).not.toContain('password-a');
  });

  it('syncOrders rejects duplicate in-flight calls for the same account locally', async () => {
    let resolveSync: (value: unknown) => void = () => {};
    setMockResponse(
      'post',
      '/api/xianyu/accounts/1/sync-orders',
      new Promise((resolve) => {
        resolveSync = resolve;
      }),
      { max_pages: 10 },
    );

    const first = syncOrders(1);
    const second = syncOrders(1);

    await expect(second).rejects.toThrow('该账号订单同步正在进行中，请稍后再试');
    expect(getMockCalls('post', '/api/xianyu/accounts/1/sync-orders')).toHaveLength(1);

    resolveSync({ success: true, fetched: 0, created_count: 0, skipped_count: 0, error: null });
    await expect(first).resolves.toMatchObject({ success: true });
  });

  it('updateAccount patches nickname and normalizes account dates', async () => {
    setMockResponse('patch', '/api/xianyu/accounts/1', {
      id: 1,
      nickname: 'new-name',
      unb: '10001',
      status: 'online',
      last_sync_at: null,
      last_error: null,
      auto_sync_enabled: false,
      auto_sync_interval_minutes: 120,
      consecutive_failures: 0,
      paused_at: null,
      created_at: '2026-07-01T12:00:00',
      updated_at: '2026-07-02T12:00:00',
    });

    const account = await updateAccount(1, { nickname: 'new-name' });

    expect(getMockCalls('patch', '/api/xianyu/accounts/1')[0].body).toEqual({ nickname: 'new-name' });
    expect(account.nickname).toBe('new-name');
    expect(account.created_at).toBeInstanceOf(Date);
    expect(account.updated_at).toBeInstanceOf(Date);
  });

  it('updateAccount patches auto_sync config and normalizes paused_at', async () => {
    setMockResponse('patch', '/api/xianyu/accounts/2', {
      id: 2,
      nickname: 'auto-account',
      unb: '20002',
      status: 'online',
      last_sync_at: '2026-07-10T08:00:00',
      last_error: null,
      auto_sync_enabled: true,
      auto_sync_interval_minutes: 90,
      consecutive_failures: 0,
      paused_at: null,
      created_at: '2026-07-01T12:00:00',
      updated_at: '2026-07-11T12:00:00',
    });

    const account = await updateAccount(2, { auto_sync_enabled: true, auto_sync_interval_minutes: 90 });

    expect(getMockCalls('patch', '/api/xianyu/accounts/2')[0].body).toEqual({
      auto_sync_enabled: true,
      auto_sync_interval_minutes: 90,
    });
    expect(account.auto_sync_enabled).toBe(true);
    expect(account.auto_sync_interval_minutes).toBe(90);
    expect(account.last_sync_at).toBeInstanceOf(Date);
  });

  it('recoverAccount posts to recover endpoint and normalizes paused_at to undefined', async () => {
    setMockResponse('post', '/api/xianyu/accounts/3/recover', {
      id: 3,
      nickname: 'paused-account',
      unb: '30003',
      status: 'online',
      last_sync_at: '2026-07-10T10:00:00',
      last_error: null,
      auto_sync_enabled: true,
      auto_sync_interval_minutes: 120,
      consecutive_failures: 0,
      paused_at: null,
      created_at: '2026-07-01T12:00:00',
      updated_at: '2026-07-11T12:00:00',
    });

    const account = await recoverAccount(3);

    expect(getMockCalls('post', '/api/xianyu/accounts/3/recover')).toHaveLength(1);
    expect(account.status).toBe('online');
    expect(account.consecutive_failures).toBe(0);
    expect(account.paused_at).toBeUndefined();
  });

  it('formatSyncResultMessage explains successful syncs with no new records', () => {
    const message = formatSyncResultMessage({
      success: true,
      fetched: 37,
      created_count: 0,
      skipped_count: 37,
    });

    expect(message).toContain('拉取 37 单');
    expect(message).toContain('无新增');
    expect(message).toContain('之前已同步');
  });

  it('hasSyncedOrdersToView is true only when sync fetched platform orders', () => {
    expect(hasSyncedOrdersToView({
      success: true,
      fetched: 37,
      created_count: 0,
      skipped_count: 37,
    })).toBe(true);

    expect(hasSyncedOrdersToView({
      success: true,
      fetched: 0,
      created_count: 0,
      skipped_count: 0,
    })).toBe(false);
  });

  it('summarizeXianyuOrders counts projected and unprojected mirror orders', () => {
    const summary = summarizeXianyuOrders([
      { projected_transaction_id: 10 },
      { projected_transaction_id: null },
      { projected_transaction_id: 0 },
      {},
    ] as any[]);

    expect(summary).toEqual({
      total: 4,
      projected: 1,
      unprojected: 3,
    });
  });

  it('formatXianyuOrderProjectionSummary explains which mirror statuses project to transactions', () => {
    const message = formatXianyuOrderProjectionSummary({
      total: 5,
      projected: 3,
      unprojected: 2,
    });

    expect(message).toContain('共 5 单');
    expect(message).toContain('已生成交易 3 单');
    expect(message).toContain('未生成交易 2 单');
    expect(message).toContain('已付款/待发货/已发货/待收货');
    expect(message).toContain('退款处理中');
    expect(message).toContain('待付款/未付款关闭');
  });

  it('filterXianyuOrdersByProjection filters mirror orders by projection status', () => {
    const orders = [
      { order_no: 'A', projected_transaction_id: 10 },
      { order_no: 'B', projected_transaction_id: null },
      { order_no: 'C', projected_transaction_id: 0 },
    ] as any[];

    expect(filterXianyuOrdersByProjection(orders, 'all').map((order) => order.order_no)).toEqual(['A', 'B', 'C']);
    expect(filterXianyuOrdersByProjection(orders, 'projected').map((order) => order.order_no)).toEqual(['A']);
    expect(filterXianyuOrdersByProjection(orders, 'unprojected').map((order) => order.order_no)).toEqual(['B', 'C']);
  });

  it('listItems normalizes sanitized account-scoped xianyu item mirrors', async () => {
    setMockResponse('get', '/api/xianyu/accounts/1/items', [
      {
        id: 10,
        account_id: 1,
        item_id: 'ITEM-A',
        title: '账号A商品',
        price: 16,
        item_status: '出售中',
        image_url: 'https://example.test/a.png',
        projected_template_id: null,
        raw_item: { secret: 'COOKIE_SENTINEL' },
        last_seen_at: '2026-07-01T12:00:00',
        created_at: '2026-07-01T12:00:00',
        updated_at: '2026-07-01T12:00:00',
      },
    ], { limit: 100 });

    const items = await listItems(1);

    expect(items[0].last_seen_at).toBeInstanceOf(Date);
    expect(items[0]).not.toHaveProperty('raw_item');
    expect(JSON.stringify(items)).not.toContain('COOKIE_SENTINEL');
  });

  it('syncItems posts account-scoped sync request', async () => {
    setMockResponse('post', '/api/xianyu/accounts/1/sync-items', {
      success: true,
      fetched: 2,
      upserted_count: 2,
      error: null,
    }, { max_pages: 5 });

    const result = await syncItems(1);

    expect(result.upserted_count).toBe(2);
    expect(getMockCalls('post', '/api/xianyu/accounts/1/sync-items')).toHaveLength(1);
  });

  it('syncItems returns a stable message for an account-level sync conflict', async () => {
    setMockError(
      'post',
      '/api/xianyu/accounts/1/sync-items',
      409,
      'running',
      { max_pages: 5 },
    );

    await expect(syncItems(1)).rejects.toThrow('该账号商品同步正在进行中，请稍后再试');
  });

  it('syncItems rejects duplicate in-flight calls for the same account locally', async () => {
    let resolveSync: (value: unknown) => void = () => {};
    setMockResponse(
      'post',
      '/api/xianyu/accounts/1/sync-items',
      new Promise((resolve) => {
        resolveSync = resolve;
      }),
      { max_pages: 5 },
    );

    const first = syncItems(1);
    const second = syncItems(1);

    await expect(second).rejects.toThrow('该账号商品同步正在进行中，请稍后再试');
    expect(getMockCalls('post', '/api/xianyu/accounts/1/sync-items')).toHaveLength(1);

    resolveSync({ success: true, fetched: 0, upserted_count: 0, error: null });
    await expect(first).resolves.toMatchObject({ success: true });
  });

  it('importXianyuItemsAsTemplates imports selected mirror ids with template defaults', async () => {
    setMockResponse('post', '/api/xianyu/accounts/1/items/import-templates', {
      created_count: 1,
      skipped_count: 1,
    });

    const result = await importXianyuItemsAsTemplates(1, [10, 11], {
      default_cost: 12.5,
      warranty_days: 90,
    });

    expect(result).toEqual({ created_count: 1, skipped_count: 1 });
    expect(getMockCalls('post', '/api/xianyu/accounts/1/items/import-templates')[0].body).toEqual({
      mirror_ids: [10, 11],
      default_cost: 12.5,
      warranty_days: 90,
    });
  });

  it('filterXianyuItemsByTemplateProjection filters item mirrors by import status', () => {
    const items = [
      { item_id: 'A', projected_template_id: 10 },
      { item_id: 'B', projected_template_id: null },
      { item_id: 'C', projected_template_id: 0 },
    ] as any[];

    expect(filterXianyuItemsByTemplateProjection(items, 'all').map((item) => item.item_id)).toEqual(['A', 'B', 'C']);
    expect(filterXianyuItemsByTemplateProjection(items, 'imported').map((item) => item.item_id)).toEqual(['A']);
    expect(filterXianyuItemsByTemplateProjection(items, 'unimported').map((item) => item.item_id)).toEqual(['B', 'C']);
  });

  it('formatItemSyncResultMessage explains successful item syncs with no updates', () => {
    const message = formatItemSyncResultMessage({
      success: true,
      fetched: 12,
      upserted_count: 0,
    });

    expect(message).toContain('拉取 12 个商品');
    expect(message).toContain('无更新');
  });

  it('hasSyncedItemsToView is true only when sync fetched platform items', () => {
    expect(hasSyncedItemsToView({
      success: true,
      fetched: 3,
      upserted_count: 0,
    })).toBe(true);

    expect(hasSyncedItemsToView({
      success: true,
      fetched: 0,
      upserted_count: 0,
    })).toBe(false);
  });

  it('summarizeXianyuItems counts imported and unimported item mirrors', () => {
    const summary = summarizeXianyuItems([
      { projected_template_id: 10 },
      { projected_template_id: null },
      { projected_template_id: 0 },
      {},
    ] as any[]);

    expect(summary).toEqual({
      total: 4,
      imported: 1,
      unimported: 3,
    });
  });
});
