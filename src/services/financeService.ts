// 财务统计服务 - 数据层迁移第二批：走后端 API。
// 所有聚合（overview/trend/monthly/产品利润/客户价值/新客户数/渠道占比）由后端完成，
// 前端仅负责调用与返回值透传（统计结构无 Date 字段，无需归一化）。
import type {
  FinanceOverview, TrendPoint, ProductProfitStat, CustomerValueStat, MonthlyComparisonPoint,
  ChannelType, ChannelBreakdownItem, BackfillCostResult,
} from '@/types';
import { apiClient } from './apiClient';

// 收支总览（本月 + 环比）
export async function getFinanceOverview(channel?: ChannelType): Promise<FinanceOverview> {
  const params: Record<string, string> = {};
  if (channel) params.channel = channel;
  return apiClient.get<FinanceOverview>('/api/finance/overview', params);
}

// 收支总览（自定义时间范围）
export async function getFinanceOverviewByRange(start: Date, end: Date, channel?: ChannelType): Promise<FinanceOverview> {
  const params: Record<string, string> = {
    start: start.toISOString(),
    end: end.toISOString(),
  };
  if (channel) params.channel = channel;
  return apiClient.get<FinanceOverview>('/api/finance/overview-by-range', params);
}

// 趋势数据
export async function getTrend(days = 30, channel?: ChannelType): Promise<TrendPoint[]> {
  const params: Record<string, string | number> = { days };
  if (channel) params.channel = channel;
  return apiClient.get<TrendPoint[]>('/api/finance/trend', params);
}

// 月度对比
export async function getMonthlyComparison(months = 6, channel?: ChannelType): Promise<MonthlyComparisonPoint[]> {
  const params: Record<string, string | number> = { months };
  if (channel) params.channel = channel;
  return apiClient.get<MonthlyComparisonPoint[]>('/api/finance/monthly-comparison', params);
}

// 商品利润排行
export async function getProductProfitStats(start?: Date, end?: Date, channel?: ChannelType): Promise<ProductProfitStat[]> {
  const params: Record<string, string> = {};
  if (start && end) {
    params.start = start.toISOString();
    params.end = end.toISOString();
  }
  if (channel) params.channel = channel;
  return apiClient.get<ProductProfitStat[]>('/api/finance/products', params);
}

// 销售渠道占比（用于财务报表渠道拆分展示）
export async function getChannelBreakdown(start: Date, end: Date): Promise<ChannelBreakdownItem[]> {
  return apiClient.get<ChannelBreakdownItem[]>('/api/finance/channel-breakdown', {
    start: start.toISOString(),
    end: end.toISOString(),
  });
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

// 一次性回填历史 cost_price=0 交易的成本价与模板关联
// 只回填 cost_price=0 的交易，不覆盖手动设置的成本。
// 通过 xianyu_orders 镜像 raw_order.itemId 反查 product_templates.source_xianyu_item_id 匹配模板。
// 后端限流 3 次/分钟（写操作 + 全表扫描 + 客户统计重算，开销大）。
export async function backfillCost(): Promise<BackfillCostResult> {
  return apiClient.post<BackfillCostResult>('/api/finance/backfill-cost');
}
