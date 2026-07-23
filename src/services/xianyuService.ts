// 闲鱼账号与订单同步服务 - 调用后端 API。
// 与现有 service 命名风格一致（listXxx/createXxx/deleteXxx）。
import { apiClient, isApiError } from './apiClient';
import type {
  CookieCloudConfigStatus,
  XianyuAccount,
  XianyuAccountInput,
  XianyuAccountTestResult,
  XianyuItem,
  XianyuItemImportResult,
  XianyuItemSyncResult,
  XianyuOrder,
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
    paused_at: toDate(a.paused_at),
    created_at: new Date(a.created_at),
    updated_at: new Date(a.updated_at),
  };
}

function normalizeOrder(o: any): XianyuOrder {
  const { raw_order: _rawOrder, ...safeOrder } = o;
  return {
    ...safeOrder,
    trade_at: toDate(o.trade_at),
    last_seen_at: new Date(o.last_seen_at),
    created_at: new Date(o.created_at),
    updated_at: new Date(o.updated_at),
  };
}

function normalizeItem(i: any): XianyuItem {
  const { raw_item: _rawItem, ...safeItem } = i;
  return {
    ...safeItem,
    last_seen_at: new Date(i.last_seen_at),
    created_at: new Date(i.created_at),
    updated_at: new Date(i.updated_at),
  };
}

// 列出闲鱼账号
const SYNC_RUNNING_MESSAGE = '该账号订单同步正在进行中，请稍后再试';
const ITEM_SYNC_RUNNING_MESSAGE = '该账号商品同步正在进行中，请稍后再试';
const syncingAccountIds = new Set<number>();
const syncingItemAccountIds = new Set<number>();

export function formatSyncResultMessage(result: XianyuSyncResult): string {
  if (result.success) {
    if (result.fetched > 0 && result.created_count === 0) {
      return `同步完成：拉取 ${result.fetched} 单，无新增。订单之前已同步或不是成交订单，已按订单号安全跳过 ${result.skipped_count} 笔。`;
    }
    return `同步完成：拉取 ${result.fetched} 单，新增 ${result.created_count} 笔，跳过 ${result.skipped_count} 笔。`;
  }
  return `同步未完成：${result.error || '未知原因'}（已写入 ${result.created_count} 笔）`;
}

export function hasSyncedOrdersToView(result: XianyuSyncResult): boolean {
  return result.fetched > 0;
}

export function formatItemSyncResultMessage(result: XianyuItemSyncResult): string {
  if (result.success) {
    if (result.fetched > 0 && result.upserted_count === 0) {
      return `商品同步完成：拉取 ${result.fetched} 个商品，无更新。商品之前已同步，或平台返回内容与镜像一致。`;
    }
    return `商品同步完成：拉取 ${result.fetched} 个商品，更新 ${result.upserted_count} 个镜像。`;
  }
  return `商品同步未完成：${result.error || '未知原因'}（已更新 ${result.upserted_count} 个镜像）`;
}

export function hasSyncedItemsToView(result: XianyuItemSyncResult): boolean {
  return result.fetched > 0;
}

export function summarizeXianyuOrders(
  orders: Pick<XianyuOrder, 'projected_transaction_id'>[],
): { total: number; projected: number; unprojected: number } {
  const total = orders.length;
  const projected = orders.filter((order) => Boolean(order.projected_transaction_id)).length;
  return {
    total,
    projected,
    unprojected: total - projected,
  };
}

export function formatXianyuOrderProjectionSummary(summary: {
  total: number;
  projected: number;
  unprojected: number;
}): string {
  return (
    `共 ${summary.total} 单 · 已生成交易 ${summary.projected} 单 · 未生成交易 ${summary.unprojected} 单。` +
    '已付款/待发货/已发货/待收货会生成待发货交易，退款处理中会生成售后中交易；待付款/未付款关闭只保留镜像。'
  );
}

export function summarizeXianyuItems(
  items: Pick<XianyuItem, 'projected_template_id'>[],
): { total: number; imported: number; unimported: number } {
  const total = items.length;
  const imported = items.filter((item) => Boolean(item.projected_template_id)).length;
  return {
    total,
    imported,
    unimported: total - imported,
  };
}

export type XianyuOrderProjectionFilter = 'all' | 'projected' | 'unprojected';

export function filterXianyuOrdersByProjection(
  orders: XianyuOrder[],
  filter: XianyuOrderProjectionFilter,
): XianyuOrder[] {
  if (filter === 'all') return orders;
  return orders.filter((order) => {
    const projected = Boolean(order.projected_transaction_id);
    return filter === 'projected' ? projected : !projected;
  });
}

export type XianyuItemTemplateProjectionFilter = 'all' | 'imported' | 'unimported';

export function filterXianyuItemsByTemplateProjection(
  items: XianyuItem[],
  filter: XianyuItemTemplateProjectionFilter,
): XianyuItem[] {
  if (filter === 'all') return items;
  return items.filter((item) => {
    const imported = Boolean(item.projected_template_id);
    return filter === 'imported' ? imported : !imported;
  });
}

export async function listAccounts(): Promise<XianyuAccount[]> {
  const list = await apiClient.get<any[]>('/api/xianyu/accounts');
  return list.map(normalizeAccount);
}

// 创建闲鱼账号（粘贴 Cookie）
export async function createAccount(input: XianyuAccountInput): Promise<XianyuAccount> {
  const a = await apiClient.post<any>('/api/xianyu/accounts', input);
  return normalizeAccount(a);
}

// 更新闲鱼账号（更新 Cookie、昵称或自动同步配置）
export async function updateAccount(
  id: number,
  patch: {
    nickname?: string;
    cookies?: string;
    auto_sync_enabled?: boolean;
    auto_sync_interval_minutes?: number;
  }
): Promise<XianyuAccount> {
  const a = await apiClient.patch<any>(`/api/xianyu/accounts/${id}`, patch);
  return normalizeAccount(a);
}

// 从熔断暂停状态恢复（需先更新 Cookie）
export async function recoverAccount(id: number): Promise<XianyuAccount> {
  const a = await apiClient.post<any>(`/api/xianyu/accounts/${id}/recover`);
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

export async function getCookieCloudConfigStatus(): Promise<CookieCloudConfigStatus> {
  return apiClient.get<CookieCloudConfigStatus>('/api/xianyu/cookiecloud/status');
}

// 触发订单同步
export async function syncOrders(id: number, maxPages = 10): Promise<XianyuSyncResult> {
  if (syncingAccountIds.has(id)) {
    throw new Error(SYNC_RUNNING_MESSAGE);
  }
  syncingAccountIds.add(id);
  try {
    return await apiClient.post<XianyuSyncResult>(
      `/api/xianyu/accounts/${id}/sync-orders`,
      undefined,
      { max_pages: maxPages },
    );
  } catch (err) {
    if (isApiError(err, 409)) {
      throw new Error(SYNC_RUNNING_MESSAGE);
    }
    throw err;
  } finally {
    syncingAccountIds.delete(id);
  }
}

// 查询账号的订单镜像；后端不会返回 raw_order
export async function listOrders(id: number, limit = 100): Promise<XianyuOrder[]> {
  const list = await apiClient.get<any[]>(`/api/xianyu/accounts/${id}/orders`, { limit });
  return list.map(normalizeOrder);
}

export async function syncItems(id: number, maxPages = 5): Promise<XianyuItemSyncResult> {
  if (syncingItemAccountIds.has(id)) {
    throw new Error(ITEM_SYNC_RUNNING_MESSAGE);
  }
  syncingItemAccountIds.add(id);
  try {
    return await apiClient.post<XianyuItemSyncResult>(
      `/api/xianyu/accounts/${id}/sync-items`,
      undefined,
      { max_pages: maxPages },
    );
  } catch (err) {
    if (isApiError(err, 409)) {
      throw new Error(ITEM_SYNC_RUNNING_MESSAGE);
    }
    throw err;
  } finally {
    syncingItemAccountIds.delete(id);
  }
}

export async function listItems(id: number, limit = 100): Promise<XianyuItem[]> {
  const list = await apiClient.get<any[]>(`/api/xianyu/accounts/${id}/items`, { limit });
  return list.map(normalizeItem);
}

export async function importXianyuItemsAsTemplates(
  id: number,
  mirrorIds: number[],
  options: { default_cost?: number; warranty_days?: number } = {},
): Promise<XianyuItemImportResult> {
  return apiClient.post<XianyuItemImportResult>(
    `/api/xianyu/accounts/${id}/items/import-templates`,
    {
      mirror_ids: mirrorIds,
      default_cost: options.default_cost ?? 0,
      warranty_days: options.warranty_days ?? 30,
    },
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
