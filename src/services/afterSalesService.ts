// 售后工单服务 - 数据层迁移第一批：走后端 API。
// 状态机 + 交易状态联动由后端 update_status 完成。
import type { AfterSales, AfterSalesInput, AfterSalesStatus, SolutionType } from '@/types';
import { apiClient, ApiException, isApiError } from './apiClient';

// 日期归一化
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeAfterSales(a: any): AfterSales {
  return {
    ...a,
    created_at: toDate(a.created_at),
    resolved_at: toDate(a.resolved_at),
    deleted_at: toDate(a.deleted_at),
    attachments: a.attachments ?? [],
  };
}

// 创建售后工单
export async function createAfterSales(input: AfterSalesInput): Promise<AfterSales> {
  const a = await apiClient.post<any>('/api/aftersales', input);
  return normalizeAfterSales(a);
}

// 获取工单
export async function getAfterSales(id: number): Promise<AfterSales | undefined> {
  try {
    const a = await apiClient.get<any>(`/api/aftersales/${id}`);
    return normalizeAfterSales(a);
  } catch (err) {
    if (isApiError(err, 404)) return undefined;
    throw err;
  }
}

// 列表
export async function listAfterSales(): Promise<AfterSales[]> {
  const list = await apiClient.get<any[]>('/api/aftersales');
  return list.map(normalizeAfterSales);
}

// 按交易查询
export async function listByTransaction(transactionId: number): Promise<AfterSales[]> {
  const list = await apiClient.get<any[]>(`/api/aftersales/by-transaction/${transactionId}`);
  return list.map(normalizeAfterSales);
}

// 软删除售后工单
export async function deleteAfterSales(id: number): Promise<void> {
  await apiClient.delete(`/api/aftersales/${id}`);
}

// 更新状态
export async function updateStatus(
  id: number,
  status: AfterSalesStatus,
  solution?: { type: SolutionType; desc?: string }
): Promise<void> {
  const body: any = { status };
  if (solution) {
    body.solution_type = solution.type;
    body.solution_desc = solution.desc;
  }
  await apiClient.patch(`/api/aftersales/${id}`, body);
}

// 待处理工单数
export async function getPendingCount(): Promise<number> {
  const r = await apiClient.get<{ pendingCount: number }>('/api/aftersales/stats');
  return r.pendingCount;
}

// 售后统计
export async function getAfterSalesStats(): Promise<{
  totalCount: number;
  pendingCount: number;
  resolvedCount: number;
  avgDurationHours: number;
  rate: number;
}> {
  return apiClient.get('/api/aftersales/stats');
}

// 高频问题商品
export async function getTopIssueProducts(limit = 10): Promise<{ productName: string; count: number }[]> {
  return apiClient.get('/api/aftersales/top-issues', { limit });
}
