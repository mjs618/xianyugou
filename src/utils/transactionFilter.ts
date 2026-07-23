// 交易列表筛选纯函数 —— 从 TransactionList.tsx 的 useEffect 中提取，
// 使筛选逻辑可独立单元测试（无需 jsdom / 组件渲染）。
//
// 筛选顺序：status → channel → keyword → dateRange → timeFilter → warrantyUrgent
// 顺序与原 useEffect 完全一致，保证行为等价。
import dayjs from 'dayjs';
import type { Transaction } from '@/types';
import { getWarrantyStatus } from './warranty';

export interface TransactionFilterOptions {
  statusFilter: string;          // 'all' | TransactionStatus
  channelFilter: string;         // 'all' | ChannelType
  keyword: string;
  dateRange: [dayjs.Dayjs, dayjs.Dayjs] | null;
  timeFilter: 'all' | 'today' | 'week' | 'month';
  warrantyUrgentOnly: boolean;
  customers: Map<number, string>;  // customer_id → name（keyword 搜索买家昵称用）
}

/**
 * 对交易列表应用组合筛选。
 *
 * 任何筛选项为 'all' / 空 / null / false 时视为"不筛选"。
 * 筛选是 AND 关系：同时设置多个条件时必须全部满足。
 */
export function filterTransactions(
  data: Transaction[],
  options: TransactionFilterOptions,
): Transaction[] {
  let result = data;

  if (options.statusFilter !== 'all') {
    result = result.filter((t) => t.status === options.statusFilter);
  }
  if (options.channelFilter !== 'all') {
    result = result.filter((t) => t.channel === options.channelFilter);
  }
  if (options.keyword) {
    const lower = options.keyword.toLowerCase();
    result = result.filter(
      (t) =>
        t.product_name.toLowerCase().includes(lower) ||
        (t.xianyu_order_no || '').toLowerCase().includes(lower) ||
        (options.customers.get(t.customer_id) || '').toLowerCase().includes(lower),
    );
  }
  if (options.dateRange) {
    const [start, end] = options.dateRange;
    result = result.filter((t) => {
      const tt = dayjs(t.trade_at);
      return tt.isAfter(start.startOf('day')) && tt.isBefore(end.endOf('day'));
    });
  }
  if (options.timeFilter !== 'all') {
    result = result.filter((t) => {
      const now = new Date();
      const tradeDate = new Date(t.trade_at);
      if (options.timeFilter === 'today') {
        if (tradeDate.toDateString() !== now.toDateString()) return false;
      } else if (options.timeFilter === 'week') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        if (tradeDate < weekAgo) return false;
      } else if (options.timeFilter === 'month') {
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        if (tradeDate < monthAgo) return false;
      }
      return true;
    });
  }
  if (options.warrantyUrgentOnly) {
    result = result.filter((t) => {
      if (!t.warranty_end) return false;
      const ws = getWarrantyStatus(t.warranty_end);
      return ws.type === 'urgent';
    });
  }

  return result;
}
