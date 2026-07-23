import dayjs from 'dayjs';
import { AFTER_SALES_PENDING_OVERDUE_HOURS, AFTER_SALES_PROCESSING_OVERDUE_HOURS } from '@/config/constants';
import type { AfterSalesStatus, SolutionType, AfterSales } from '@/types';

export const AFTER_SALES_PAGE_SIZE = 20;

export const statusMap: Record<AfterSalesStatus, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'red' },
  processing: { label: '处理中', color: 'orange' },
  resolved: { label: '已解决', color: 'green' },
  closed: { label: '已关闭', color: 'default' },
};

export const solutionMap: Record<SolutionType, string> = {
  remote: '远程协助',
  reship: '重新发货',
  refund: '退款',
  other: '其他',
};

/** 返回工单超时小时数；非超时状态或未超时返回 0。 */
export function getAfterSalesOverdueHours(ticket: AfterSales): number {
  if (ticket.status !== 'pending' && ticket.status !== 'processing') return 0;
  const threshold = ticket.status === 'pending'
    ? AFTER_SALES_PENDING_OVERDUE_HOURS
    : AFTER_SALES_PROCESSING_OVERDUE_HOURS;
  const elapsed = dayjs().diff(dayjs(ticket.created_at), 'hour');
  return elapsed > threshold ? elapsed : 0;
}
