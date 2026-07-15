import type { XianyuAccount } from '@/types';

export interface OrderSyncOverviewData {
  total: number;
  needsAttention: number;
  autoSyncActive: number;
  pausedNames: string[];
}

const ATTENTION_STATUSES = new Set<XianyuAccount['status']>(['paused', 'invalid', 'risk']);

export function getOrderSyncOverview(accounts: XianyuAccount[]): OrderSyncOverviewData {
  return {
    total: accounts.length,
    needsAttention: accounts.filter((account) => ATTENTION_STATUSES.has(account.status)).length,
    autoSyncActive: accounts.filter(
      (account) => account.auto_sync_enabled && account.status !== 'paused',
    ).length,
    pausedNames: accounts
      .filter((account) => account.status === 'paused')
      .map((account) => account.nickname),
  };
}
