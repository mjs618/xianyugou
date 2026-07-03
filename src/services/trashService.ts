// 回收站服务 - 数据层迁移最后一批：走后端 API。
// 列出/恢复/彻底删除/过期清理均由后端完成。
// 注意：附件清理由后端在 purge 时处理（attachment 留本地，purge 不删本地附件 Blob，
// 因交易数据已迁后端，本地 attachments 表与后端交易脱钩，附件管理后续单独处理）。
import type { Customer, Transaction, AfterSales } from '@/types';
import { apiClient } from './apiClient';

// 软删除保留天数（Settings 页显示用，与后端一致）
export const SOFT_DELETE_RETENTION_DAYS = 30;
export const AUDIT_LOG_RETENTION_DAYS = 90;
export const NOTIFICATION_RETENTION_DAYS = 30;

// 日期归一化
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeCustomer(c: any): Customer {
  return { ...c, deleted_at: toDate(c.deleted_at), created_at: new Date(c.created_at), updated_at: new Date(c.updated_at), tags: c.tags ?? [] };
}
function normalizeTransaction(t: any): Transaction {
  return { ...t, trade_at: new Date(t.trade_at), deleted_at: toDate(t.deleted_at), updated_at: new Date(t.updated_at), attachments: t.attachments ?? [] };
}
function normalizeAfterSales(a: any): AfterSales {
  return { ...a, deleted_at: toDate(a.deleted_at), created_at: toDate(a.created_at), attachments: a.attachments ?? [] };
}

// ==================== 列出软删除记录 ====================

export async function listTrashedCustomers(): Promise<Customer[]> {
  const list = await apiClient.get<any[]>('/api/trash/customers');
  return list.map(normalizeCustomer);
}

export async function listTrashedTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/trash/transactions');
  return list.map(normalizeTransaction);
}

export async function listTrashedAfterSales(): Promise<AfterSales[]> {
  const list = await apiClient.get<any[]>('/api/trash/after-sales');
  return list.map(normalizeAfterSales);
}

// ==================== 恢复 ====================

export async function restoreCustomer(id: number): Promise<void> {
  await apiClient.post(`/api/trash/customers/${id}/restore`);
}

export async function restoreTransaction(id: number): Promise<void> {
  await apiClient.post(`/api/trash/transactions/${id}/restore`);
}

export async function restoreAfterSales(id: number): Promise<void> {
  await apiClient.post(`/api/trash/after-sales/${id}/restore`);
}

// ==================== 彻底删除 ====================

export async function purgeCustomer(id: number): Promise<void> {
  await apiClient.delete(`/api/trash/customers/${id}/purge`);
}

export async function purgeTransaction(id: number): Promise<void> {
  await apiClient.delete(`/api/trash/transactions/${id}/purge`);
}

export async function purgeAfterSales(id: number): Promise<void> {
  await apiClient.delete(`/api/trash/after-sales/${id}/purge`);
}

// ==================== 过期清理（应用启动时调用）====================

// 后端在 lifespan 启动时不会自动清理（避免每次重启扫表）。
// 前端启动时触发一次清理（轻量 HTTP 调用，后端按 30 天阈值清理）。
// 当前后端未暴露清理端点，此函数为 no-op，清理由后端定时任务或手动触发。
export async function cleanupExpiredSoftDeletes(): Promise<{ customers: number; transactions: number; afterSales: number }> {
  // TODO: 后端可加 /api/trash/cleanup 端点。当前返回空结果。
  return { customers: 0, transactions: 0, afterSales: 0 };
}

export async function cleanupOldLogs(): Promise<number> {
  return 0;
}

export async function cleanupOldNotifications(): Promise<number> {
  return 0;
}

export async function runAllCleanup(): Promise<void> {
  // 数据已迁后端，过期清理由后端负责。前端启动不再扫描本地表。
  return;
}
