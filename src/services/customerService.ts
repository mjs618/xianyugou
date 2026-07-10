// 客户服务 - 数据层迁移第一批：CRUD 走后端 API，纯函数保留。
//
// 切换说明：
// - createCustomer/listCustomers/getCustomer/updateCustomer/softDeleteCustomer/toggleBlacklist
//   /searchCustomers/findByNickname/getRecentCustomers → 调用后端 API
// - 纯函数保留：evaluateLevelWithSettings / isChurnRisk / isHighValueChurnRisk / getChurnRiskStats
// - setCustomerTags 委托 customerTagService
import type { Customer, CustomerLevel, Transaction } from '@/types';
import { apiClient, isApiError } from './apiClient';

// 客户等级自动评定（BR-4）
export function evaluateLevelWithSettings(
  totalSpent: number,
  tradeCount: number,
  settings: { vip_threshold: number; core_threshold: number; vip_trade_count: number; core_trade_count: number }
): CustomerLevel {
  if (totalSpent >= settings.core_threshold || tradeCount >= settings.core_trade_count) return 'core';
  if (totalSpent >= settings.vip_threshold || tradeCount >= settings.vip_trade_count) return 'vip';
  return 'normal';
}

// 流失风险判定阈值（统一口径，消除 Dashboard 与 CustomerList 的不一致）
export const CHURN_RISK_DAYS = 30;
export const HIGH_VALUE_CHURN_DAYS = 60;

export function isChurnRisk(lastTradeAt: Date | undefined): boolean {
  if (!lastTradeAt) return false;
  const days = Math.floor((Date.now() - new Date(lastTradeAt).getTime()) / (24 * 60 * 60 * 1000));
  return days > CHURN_RISK_DAYS;
}

export function isHighValueChurnRisk(lastTradeAt: Date | undefined, level: CustomerLevel): boolean {
  if (!lastTradeAt || (level !== 'vip' && level !== 'core')) return false;
  const days = Math.floor((Date.now() - new Date(lastTradeAt).getTime()) / (24 * 60 * 60 * 1000));
  return days > HIGH_VALUE_CHURN_DAYS;
}

export function getChurnRiskStats(
  customers: Customer[],
  trades: Transaction[]
): { blacklistCount: number; churnRiskCount: number } {
  const lastTradeMap = new Map<number, Date>();
  for (const t of trades) {
    if (t.deleted_at) continue;
    const cur = lastTradeMap.get(t.customer_id);
    const d = new Date(t.trade_at);
    if (!cur || d.getTime() > cur.getTime()) {
      lastTradeMap.set(t.customer_id, d);
    }
  }
  let blacklistCount = 0;
  let churnRiskCount = 0;
  for (const c of customers) {
    if (c.is_blacklist) blacklistCount++;
    if (c.id !== undefined && isHighValueChurnRisk(lastTradeMap.get(c.id), c.level)) {
      churnRiskCount++;
    }
  }
  return { blacklistCount, churnRiskCount };
}

// ==================== 日期归一化（后端 ISO 字符串 → Date）====================
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeCustomer(c: any): Customer {
  return {
    ...c,
    first_trade_at: toDate(c.first_trade_at),
    created_at: new Date(c.created_at),
    updated_at: new Date(c.updated_at),
    deleted_at: toDate(c.deleted_at),
    tags: c.tags ?? [],
  };
}

// ==================== API CRUD ====================

export async function createCustomer(input: {
  xianyu_nickname: string;
  contact_info?: string;
  notes?: string;
  is_blacklist?: boolean;
}): Promise<Customer> {
  const c = await apiClient.post<any>('/api/customers', input);
  return normalizeCustomer(c);
}

export async function findByNickname(nickname: string): Promise<Customer | undefined> {
  // 后端无按昵称查的专用端点，用 search 兼容（取第一条精确匹配）
  const lower = nickname.trim().toLowerCase();
  const list = await apiClient.get<any[]>('/api/customers', { keyword: nickname });
  return list.map(normalizeCustomer).find((c) => c.xianyu_nickname.toLowerCase() === lower);
}

export async function listCustomers(): Promise<Customer[]> {
  const list = await apiClient.get<any[]>('/api/customers');
  return list.map(normalizeCustomer);
}

export async function searchCustomers(keyword: string): Promise<Customer[]> {
  const list = await apiClient.get<any[]>('/api/customers', { keyword });
  return list.map(normalizeCustomer);
}

export async function getCustomer(id: number): Promise<Customer | undefined> {
  try {
    const c = await apiClient.get<any>(`/api/customers/${id}`);
    return normalizeCustomer(c);
  } catch (err) {
    if (isApiError(err, 404)) return undefined;
    throw err;
  }
}

export async function updateCustomer(id: number, patch: Partial<Customer>): Promise<void> {
  // 携带乐观锁 version；后端不匹配返回 409
  const expected_version = patch.version;
  const body = { ...patch };
  delete body.version;
  delete body.created_at;
  delete body.updated_at;
  try {
    await apiClient.patch(`/api/customers/${id}`, { ...body, expected_version });
  } catch (err) {
    if (isApiError(err, 409)) {
      throw new Error('客户已被其他操作修改，请刷新后重试');
    }
    throw err;
  }
}

export async function softDeleteCustomer(id: number): Promise<void> {
  await apiClient.delete(`/api/customers/${id}`);
}

export async function toggleBlacklist(id: number): Promise<void> {
  await apiClient.post(`/api/customers/${id}/toggle-blacklist`);
}

// 最近客户：后端无专用端点，用客户列表按累计消费降序近似（高价值客户优先展示）
// 被 CustomerSelect 组件使用，供快速选择
export async function getRecentCustomers(limit = 5): Promise<Customer[]> {
  const all = await listCustomers();
  return all
    .slice()
    .sort((a, b) => b.total_spent - a.total_spent)
    .slice(0, limit);
}

// 设置客户标签（委托 customerTagService）
export async function setCustomerTags(customerId: number, tags: string[]): Promise<void> {
  const { setCustomerTags: setTags } = await import('./customerTagService');
  await setTags(customerId, tags);
}
