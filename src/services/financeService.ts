// 财务统计服务 - 数据层迁移第二批：走后端 API。
// 所有聚合（overview/trend/monthly/产品利润/客户价值/新客户数）由后端完成，
// 前端仅负责调用与返回值透传（统计结构无 Date 字段，无需归一化）。
import type {
  FinanceOverview, TrendPoint, ProductProfitStat, CustomerValueStat, MonthlyComparisonPoint,
} from '@/types';
import { apiClient } from './apiClient';

// 收支总览（本月 + 环比）
export async function getFinanceOverview(): Promise<FinanceOverview> {
  return apiClient.get<FinanceOverview>('/api/finance/overview');
}

// 收支总览（自定义时间范围）
export async function getFinanceOverviewByRange(start: Date, end: Date): Promise<FinanceOverview> {
  return apiClient.get<FinanceOverview>('/api/finance/overview-by-range', {
    start: start.toISOString(),
    end: end.toISOString(),
  });
}

// 趋势数据
export async function getTrend(days = 30): Promise<TrendPoint[]> {
  return apiClient.get<TrendPoint[]>('/api/finance/trend', { days });
}

// 月度对比
export async function getMonthlyComparison(months = 6): Promise<MonthlyComparisonPoint[]> {
  return apiClient.get<MonthlyComparisonPoint[]>('/api/finance/monthly-comparison', { months });
}

// 商品利润排行
export async function getProductProfitStats(start?: Date, end?: Date): Promise<ProductProfitStat[]> {
  const params: Record<string, string> = {};
  if (start && end) {
    params.start = start.toISOString();
    params.end = end.toISOString();
  }
  return apiClient.get<ProductProfitStat[]>('/api/finance/products', params);
}

// 客户价值排行
export async function getCustomerValueStats(limit = 10): Promise<CustomerValueStat[]> {
  return apiClient.get<CustomerValueStat[]>('/api/finance/customers', { limit });
}

// 本月新客户数
export async function getNewCustomerCount(): Promise<number> {
  const r = await apiClient.get<{ count: number }>('/api/finance/new-customer-count');
  return r.count;
}

// 指定时间范围新客户数
export async function getNewCustomerCountByRange(start: Date, end: Date): Promise<number> {
  const r = await apiClient.get<{ count: number }>('/api/finance/new-customer-count', {
    start: start.toISOString(),
    end: end.toISOString(),
  });
  return r.count;
}
