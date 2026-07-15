import { apiClient } from './apiClient';

export interface AccountMetrics {
  total: number;
  online: number;
  paused: number;
  invalid: number;
}

export interface SyncMetrics {
  last_24h_success: number;
  last_24h_failed: number;
  last_24h_fetched_orders: number;
  last_24h_created_transactions: number;
  last_error: string | null;
  last_sync_at: string | null;
}

export interface BackupMetrics {
  last_backup_at: string | null;
  backup_count: number;
  backup_dir_exists: boolean;
}

export interface MetricsResponse {
  timestamp: string;
  accounts: AccountMetrics;
  sync: SyncMetrics;
  backup: BackupMetrics;
  notifications_unread: number;
  scheduler_running: boolean;
}

export function getMetrics(): Promise<MetricsResponse> {
  return apiClient.get<MetricsResponse>('/api/metrics');
}
