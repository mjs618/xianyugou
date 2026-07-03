// 质保监控服务 - 数据层迁移第二批：走后端 API。
// 查询/延长/提前结束/历史记录均调用后端 /api/warranty。
import type { Transaction, WarrantyExtension } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化（后端 ISO 字符串 → Date）
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeTransaction(t: any): Transaction {
  return {
    ...t,
    trade_at: new Date(t.trade_at),
    warranty_end: toDate(t.warranty_end),
    created_at: new Date(t.created_at),
    updated_at: new Date(t.updated_at),
    deleted_at: toDate(t.deleted_at),
    attachments: t.attachments ?? [],
  };
}

function normalizeExtension(e: any): WarrantyExtension {
  return {
    ...e,
    old_end: new Date(e.old_end),
    new_end: new Date(e.new_end),
    created_at: new Date(e.created_at),
  };
}

// 查询质保中交易（未到期）
export async function getWarrantyActiveTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/warranty/active');
  return list.map(normalizeTransaction);
}

// 查询即将到期交易（3天内）
export async function getUrgentTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/warranty/urgent');
  return list.map(normalizeTransaction);
}

// 查询已过期交易
export async function getExpiredTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/warranty/expired');
  return list.map(normalizeTransaction);
}

// 查询所有有质保的交易
export async function getAllWarrantyTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/warranty/all');
  return list.map(normalizeTransaction);
}

// 延长质保（后端记录历史 + 更新交易）
export async function extendWarranty(transactionId: number, days: number, reason?: string): Promise<void> {
  await apiClient.post(`/api/warranty/${transactionId}/extend`, { days, reason });
}

// 提前结束质保
export async function endWarrantyEarly(transactionId: number, reason?: string): Promise<void> {
  await apiClient.post(`/api/warranty/${transactionId}/end-early`, { reason });
}

// 获取质保延长历史
export async function getWarrantyExtensions(transactionId: number): Promise<WarrantyExtension[]> {
  const list = await apiClient.get<any[]>(`/api/warranty/${transactionId}/extensions`);
  return list.map(normalizeExtension);
}
