import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  getFinanceOverview,
  getFinanceOverviewByRange,
  getTrend,
  getMonthlyComparison,
  getProductProfitStats,
  getCustomerValueStats,
  getNewCustomerCount,
  getNewCustomerCountByRange,
} from '@/services/financeService';

describe('financeService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('getFinanceOverview 应 GET /api/finance/overview', async () => {
    setMockResponse('get', '/api/finance/overview', {
      totalIncome: 300, totalCost: 80, totalProfit: 220, profitRate: 0.73,
      tradeCount: 2, prevIncome: 0, prevProfit: 0, prevTradeCount: 0,
      incomeChange: 1, profitChange: 1, tradeCountChange: 1,
    });
    const o = await getFinanceOverview();
    expect(o.totalIncome).toBe(300);
    expect(o.totalProfit).toBe(220);
  });

  it('getFinanceOverviewByRange 应传递 start/end', async () => {
    setMockResponse('get', '/api/finance/overview-by-range', {
      totalIncome: 500, totalCost: 100, totalProfit: 400, profitRate: 0.8,
      tradeCount: 3, prevIncome: 0, prevProfit: 0, prevTradeCount: 0,
      incomeChange: 1, profitChange: 1, tradeCountChange: 1,
    });
    await getFinanceOverviewByRange(new Date('2026-05-01'), new Date('2026-06-30'));
    const params = getMockCalls('get', '/api/finance/overview-by-range')[0].params as any;
    expect(params.start).toBeDefined();
    expect(params.end).toBeDefined();
  });

  it('getTrend 应传递 days 参数', async () => {
    setMockResponse('get', '/api/finance/trend', [
      { date: '2026-06-01', income: 100, cost: 20, profit: 80 },
    ]);
    const trend = await getTrend(30);
    expect(trend.length).toBe(1);
    expect((getMockCalls('get', '/api/finance/trend')[0].params as any).days).toBe(30);
  });

  it('getMonthlyComparison 应传递 months', async () => {
    setMockResponse('get', '/api/finance/monthly-comparison', [
      { month: '6月', income: 200, cost: 50, profit: 150, tradeCount: 2 },
    ]);
    await getMonthlyComparison(6);
    expect((getMockCalls('get', '/api/finance/monthly-comparison')[0].params as any).months).toBe(6);
  });

  it('getProductProfitStats 无范围时不传 start/end', async () => {
    setMockResponse('get', '/api/finance/products', [
      { productName: '商品A', totalProfit: 230, totalIncome: 300, count: 2, profitRate: 0.77 },
    ]);
    await getProductProfitStats();
    const params = getMockCalls('get', '/api/finance/products')[0].params as any;
    expect(params.start).toBeUndefined();
  });

  it('getProductProfitStats 有范围时应传递', async () => {
    setMockResponse('get', '/api/finance/products', []);
    await getProductProfitStats(new Date('2026-06-01'), new Date('2026-06-30'));
    const params = getMockCalls('get', '/api/finance/products')[0].params as any;
    expect(params.start).toBeDefined();
    expect(params.end).toBeDefined();
  });

  it('getCustomerValueStats 应传递 limit', async () => {
    setMockResponse('get', '/api/finance/customers', [
      { customerId: 1, nickname: '高价值', totalSpent: 500, tradeCount: 5, level: 'vip' },
    ]);
    await getCustomerValueStats(10);
    expect((getMockCalls('get', '/api/finance/customers')[0].params as any).limit).toBe(10);
  });

  it('getNewCustomerCount 本月（无参）', async () => {
    setMockResponse('get', '/api/finance/new-customer-count', { count: 3 });
    expect(await getNewCustomerCount()).toBe(3);
  });

  it('getNewCustomerCountByRange 应传递范围', async () => {
    setMockResponse('get', '/api/finance/new-customer-count', { count: 5 });
    await getNewCustomerCountByRange(new Date('2026-05-01'), new Date('2026-06-30'));
    const params = getMockCalls('get', '/api/finance/new-customer-count')[0].params as any;
    expect(params.start).toBeDefined();
    expect(params.end).toBeDefined();
  });
});
