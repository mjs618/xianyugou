// 交易服务 - 数据层迁移第一批：CRUD 走后端 API。
//
// 切换说明：
// - createTransaction/updateTransaction/softDeleteTransaction/getTransaction/listTransactions
//   /listByStatus/listByCustomer/listByDateRange/changeStatus → 调用后端 API
// - calcProfit 保留（纯函数，前端表单实时算利润用）
// - 级联（客户累计/推荐/返利/质保）由后端 create_transaction/update_transaction 自动完成
import type { Transaction, TransactionInput, TransactionStatus } from '@/types';
import { apiClient, ApiException, isApiError } from './apiClient';

// 计算利润（BR-1）
export function calcProfit(salePrice: number, costPrice: number): number {
  return Math.round((salePrice - costPrice) * 100) / 100;
}

// ==================== 日期归一化（后端 ISO 字符串 → Date）====================
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeTransaction(t: any): Transaction {
  return {
    ...t,
    trade_at: new Date(t.trade_at),
    shipped_at: toDate(t.shipped_at),
    warranty_end: toDate(t.warranty_end),
    created_at: new Date(t.created_at),
    updated_at: new Date(t.updated_at),
    deleted_at: toDate(t.deleted_at),
    attachments: t.attachments ?? [],
  };
}

// ==================== API CRUD ====================

// 创建交易（级联：客户累计、关联关系、返利、质保 —— 均由后端完成）
export async function createTransaction(input: TransactionInput): Promise<Transaction> {
  const t = await apiClient.post<any>('/api/transactions', input);
  return normalizeTransaction(t);
}

// 更新交易（乐观锁 + 级联由后端完成）
export async function updateTransaction(id: number, patch: Partial<TransactionInput>): Promise<void> {
  const body: any = { ...patch };
  // 携带乐观锁 version（若有）
  if ((patch as any).version !== undefined) {
    body.expected_version = (patch as any).version;
    delete body.version;
  }
  delete (body as any).created_at;
  delete (body as any).updated_at;
  try {
    await apiClient.patch(`/api/transactions/${id}`, body);
  } catch (err) {
    if (isApiError(err, 409)) {
      throw new Error('交易已被其他操作修改，请刷新后重试');
    }
    throw err;
  }
}

// 软删除交易（级联清理由后端完成）
export async function softDeleteTransaction(id: number): Promise<void> {
  await apiClient.delete(`/api/transactions/${id}`);
}

// 获取交易
export async function getTransaction(id: number): Promise<Transaction | undefined> {
  try {
    const t = await apiClient.get<any>(`/api/transactions/${id}`);
    return normalizeTransaction(t);
  } catch (err) {
    if (isApiError(err, 404)) return undefined;
    throw err;
  }
}

// 列表查询（未删除）
export async function listTransactions(): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/transactions', { with_name: true });
  return list.map(normalizeTransaction);
}

// 按状态查询
export async function listByStatus(status: TransactionStatus): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/transactions', { status, with_name: true });
  return list.map(normalizeTransaction);
}

// 按客户查询（按交易时间正序，与原实现一致）
export async function listByCustomer(customerId: number): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/transactions', { customer_id: customerId, with_name: true });
  // 后端默认 trade_at 倒序，此处翻转为正序以匹配原行为
  return list.map(normalizeTransaction).reverse();
}

// 按时间范围查询
export async function listByDateRange(start: Date, end: Date): Promise<Transaction[]> {
  const list = await apiClient.get<any[]>('/api/transactions', {
    start: start.toISOString(),
    end: end.toISOString(),
  });
  return list.map(normalizeTransaction);
}

// 修改交易状态
export async function changeStatus(id: number, status: TransactionStatus, version?: number): Promise<void> {
  const body: any = { status };
  if (version !== undefined) body.expected_version = version;
  try {
    await apiClient.post(`/api/transactions/${id}/status`, body);
  } catch (err) {
    if (isApiError(err, 409)) {
      throw new Error('交易已被其他操作修改，请刷新后重试');
    }
    throw err;
  }
}
