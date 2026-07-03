// 闲鱼账号与订单同步服务 - 调用后端 API。
// 与现有 service 命名风格一致（listXxx/createXxx/deleteXxx）。
import { apiClient } from './apiClient';
import type {
  XianyuAccount,
  XianyuAccountInput,
  XianyuAccountTestResult,
  XianyuSyncResult,
  XianyuSyncLog,
} from '@/types';

// 后端返回的日期是 ISO 字符串，这里统一转 Date（与现有类型对齐）
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeAccount(a: any): XianyuAccount {
  return {
    ...a,
    last_sync_at: toDate(a.last_sync_at),
    created_at: new Date(a.created_at),
    updated_at: new Date(a.updated_at),
  };
}

// 列出闲鱼账号
export async function listAccounts(): Promise<XianyuAccount[]> {
  const list = await apiClient.get<any[]>('/api/xianyu/accounts');
  return list.map(normalizeAccount);
}

// 创建闲鱼账号（粘贴 Cookie）
export async function createAccount(input: XianyuAccountInput): Promise<XianyuAccount> {
  const a = await apiClient.post<any>('/api/xianyu/accounts', input);
  return normalizeAccount(a);
}

// 更新闲鱼账号（更新 Cookie 或昵称）
export async function updateAccount(
  id: number,
  patch: { nickname?: string; cookies?: string }
): Promise<XianyuAccount> {
  const a = await apiClient.patch<any>(`/api/xianyu/accounts/${id}`, patch);
  return normalizeAccount(a);
}

// 删除闲鱼账号
export async function deleteAccount(id: number): Promise<void> {
  await apiClient.delete(`/api/xianyu/accounts/${id}`);
}

// 校验账号 Cookie 有效性
export async function testAccount(id: number): Promise<XianyuAccountTestResult> {
  return apiClient.post<XianyuAccountTestResult>(`/api/xianyu/accounts/${id}/test`);
}

// 触发订单同步
export async function syncOrders(id: number, maxPages = 10): Promise<XianyuSyncResult> {
  return apiClient.post<XianyuSyncResult>(
    `/api/xianyu/accounts/${id}/sync-orders`,
    undefined,
    { max_pages: maxPages },
  );
}

// 查询同步日志
export async function listSyncLogs(id: number, limit = 20): Promise<XianyuSyncLog[]> {
  const list = await apiClient.get<any[]>(`/api/xianyu/accounts/${id}/sync-logs`, { limit });
  return list.map((l) => ({
    ...l,
    created_at: new Date(l.created_at),
  }));
}

// 后端在线检测（委托给 apiClient）
export { checkBackend } from './apiClient';
