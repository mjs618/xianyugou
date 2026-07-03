import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { createCustomer, evaluateLevelWithSettings, updateCustomer, listCustomers, getCustomer } from '@/services/customerService';

describe('customerService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('应创建客户并归一化返回（POST /api/customers）', async () => {
    setMockResponse('post', '/api/customers', {
      id: 1, xianyu_nickname: '测试用户A', contact_info: null, first_trade_at: null,
      total_spent: 0, trade_count: 0, level: 'normal', tags: [], is_blacklist: false,
      notes: null, version: 0, created_at: '2026-06-01', updated_at: '2026-06-01',
    });
    const c = await createCustomer({ xianyu_nickname: '测试用户A' });
    expect(c.id).toBe(1);
    expect(c.xianyu_nickname).toBe('测试用户A');
    expect(c.total_spent).toBe(0);
    expect(c.level).toBe('normal');
    expect(c.is_blacklist).toBe(false);
    expect(c.tags).toEqual([]);
    expect(c.created_at).toBeInstanceOf(Date); // ISO → Date
    // 验证请求体
    expect(getMockCalls('post', '/api/customers')[0].body).toMatchObject({ xianyu_nickname: '测试用户A' });
  });

  it('应正确评定客户等级（纯函数）', () => {
    const settings = { vip_threshold: 500, core_threshold: 2000, vip_trade_count: 5, core_trade_count: 20 };
    expect(evaluateLevelWithSettings(100, 1, settings)).toBe('normal');
    expect(evaluateLevelWithSettings(500, 1, settings)).toBe('vip');
    expect(evaluateLevelWithSettings(100, 5, settings)).toBe('vip');
    expect(evaluateLevelWithSettings(2000, 1, settings)).toBe('core');
    expect(evaluateLevelWithSettings(100, 20, settings)).toBe('core');
  });

  it('updateCustomer 应 PATCH 并携带 expected_version', async () => {
    setMockResponse('patch', '/api/customers/1', {
      id: 1, xianyu_nickname: 'A', total_spent: 0, trade_count: 0, level: 'normal',
      tags: [], is_blacklist: false, version: 3, created_at: '2026-06-01', updated_at: '2026-06-01',
    });
    await updateCustomer(1, { notes: '备注', version: 2 } as any);
    const calls = getMockCalls('patch', '/api/customers/1');
    expect(calls[0].body).toMatchObject({ notes: '备注', expected_version: 2 });
    expect((calls[0].body as any).version).toBeUndefined();
  });

  it('listCustomers / getCustomer 应 GET 并转换日期', async () => {
    setMockResponse('get', '/api/customers', [
      { id: 1, xianyu_nickname: 'A', total_spent: 0, trade_count: 0, level: 'normal',
        tags: [], is_blacklist: false, version: 0, created_at: '2026-06-01', updated_at: '2026-06-01' },
    ]);
    const list = await listCustomers();
    expect(list[0].created_at).toBeInstanceOf(Date);

    setMockResponse('get', '/api/customers/5', {
      id: 5, xianyu_nickname: 'B', total_spent: 100, trade_count: 1, level: 'normal',
      tags: [], is_blacklist: false, version: 0, created_at: '2026-06-01', updated_at: '2026-06-01',
    });
    const c = await getCustomer(5);
    expect(c?.id).toBe(5);
  });
});
