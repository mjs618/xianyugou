import type { PendingSummary } from '@/types';

export function getNavigationBadgeCount(path: string, summary: PendingSummary): number {
  if (path === '/warranty') return summary.warrantyUrgent;
  if (path === '/after-sales') return summary.afterSalesPending;
  if (path === '/finance') return summary.rebatePending;
  return 0;
}
