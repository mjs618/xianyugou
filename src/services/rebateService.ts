// 返利服务 - 数据层迁移第一批：走后端 API。
// 状态机校验由后端 markPaid/cancelRebate/updateStatus 完成，前端保留 VALID_TRANSITIONS 供即时校验。
import type { RebateRecord, RebateStatus, Transaction } from '@/types';
import { apiClient, ApiException, isApiError } from './apiClient';

// P-13：返利状态机合法性（前端保留供即时校验）
const VALID_REBATE_TRANSITIONS: Record<RebateStatus, RebateStatus[]> = {
  pending: ['paid', 'cancelled'],
  paid: ['cancelled'],
  cancelled: [],
};

export function validateRebateTransition(from: RebateStatus, to: RebateStatus): void {
  if (from === to) return;
  const allowed = VALID_REBATE_TRANSITIONS[from];
  if (!allowed || !allowed.includes(to)) {
    throw new Error(`非法的返利状态流转：${from} → ${to}（仅允许 pending→paid/cancelled、paid→cancelled）`);
  }
}

// 日期归一化
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeRebate(r: any): RebateRecord {
  return {
    ...r,
    paid_at: toDate(r.paid_at),
    created_at: new Date(r.created_at),
  };
}

// 列表
export async function listRebates(): Promise<RebateRecord[]> {
  const list = await apiClient.get<any[]>('/api/rebates');
  return list.map(normalizeRebate);
}

// 按介绍人查询
export async function listByReferrer(referrerId: number): Promise<RebateRecord[]> {
  const list = await apiClient.get<any[]>(`/api/rebates/by-referrer/${referrerId}`);
  return list.map(normalizeRebate);
}

// 待结算返利数
export async function getPendingCount(): Promise<number> {
  const r = await apiClient.get<{ count: number }>('/api/rebates/pending-count');
  return r.count;
}

// 待结算返利总额
export async function getPendingTotal(): Promise<number> {
  const r = await apiClient.get<{ total: number }>('/api/rebates/pending-total');
  return r.total;
}

// 累计返利总额
export async function getTotalPaid(): Promise<number> {
  // 后端无 paid-total 专用端点，从列表聚合
  const all = await listRebates();
  const paid = all.filter((r) => r.status === 'paid');
  return Math.round(paid.reduce((s, r) => s + r.amount, 0) * 100) / 100;
}

// 标记为已支付
export async function markPaid(id: number, notes?: string): Promise<void> {
  try {
    await apiClient.patch(`/api/rebates/${id}`, { status: 'paid', notes });
  } catch (err) {
    // 后端：404 = 不存在，400 = 状态非法
    if (isApiError(err, 404) || isApiError(err, 400)) {
      throw new Error('返利记录不存在或状态非法');
    }
    throw err;
  }
}

// 取消返利
export async function cancelRebate(id: number, notes?: string): Promise<void> {
  try {
    await apiClient.patch(`/api/rebates/${id}`, { status: 'cancelled', notes });
  } catch (err) {
    // 后端：404 = 不存在，400 = 状态非法
    if (isApiError(err, 404) || isApiError(err, 400)) {
      throw new Error('返利记录不存在或状态非法');
    }
    throw err;
  }
}

// 批量结算
export async function batchPay(ids: number[]): Promise<{ updated: number; skipped: number }> {
  return apiClient.post('/api/rebates/batch-pay', { ids });
}

// 按交易查询返利
export async function getRebateByTransaction(transactionId: number): Promise<RebateRecord | undefined> {
  const r = await apiClient.get<any>(`/api/rebates/by-transaction/${transactionId}`);
  return r ? normalizeRebate(r) : undefined;
}

// 更新状态
export async function updateStatus(id: number, status: RebateStatus, notes?: string): Promise<void> {
  await apiClient.patch(`/api/rebates/${id}`, { status, notes });
}

// 设置变更后重算（由后端 updateSettings 自动完成，前端保留空签名兼容）
export async function recalcPendingRebates(): Promise<number> {
  return 0;
}

// 兼容：未使用的导入占位（Transaction 类型曾用于旧实现，保留避免破坏潜在引用）
export type { Transaction };
