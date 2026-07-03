// 操作审计日志服务 - 数据层迁移第四批。
//
// 迁移说明：
// - logOperation 改为 no-op：审计日志由后端在各业务操作时自动记录（create/update/delete 等）
// - listLogs / getLogCount / clearLogs 走后端 API（后端 /api/operation-logs）
// - 前端不再写入审计日志，保留 logOperation 空签名兼容历史调用
import type { OperationLog, AuditModule } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化
function normalizeLog(l: any): OperationLog {
  return {
    ...l,
    created_at: new Date(l.created_at),
  };
}

// 记录操作日志 —— no-op（后端在各业务操作时自动记录）
// 保留签名兼容历史 `await logOperation(...)` 调用
export function logOperation(
  _module: AuditModule,
  _action: string,
  _options?: { target_id?: number; target_name?: string; detail?: string }
): Promise<void> {
  return Promise.resolve();
}

// 查询日志列表（按时间倒序，支持分页与模块筛选）
export async function listLogs(options?: {
  module?: AuditModule;
  limit?: number;
  offset?: number;
}): Promise<OperationLog[]> {
  const { module, limit = 100, offset = 0 } = options || {};
  const r = await apiClient.get<{ items: any[]; total: number }>('/api/operation-logs', {
    module, page: Math.floor(offset / limit) + 1, page_size: limit,
  });
  return (r.items || []).map(normalizeLog);
}

// 获取日志总数
export async function getLogCount(module?: AuditModule): Promise<number> {
  const r = await apiClient.get<{ items: any[]; total: number }>('/api/operation-logs', {
    module, page: 1, page_size: 1,
  });
  return r.total ?? 0;
}

// 清空所有日志
export async function clearLogs(): Promise<void> {
  await apiClient.delete('/api/operation-logs');
}

// 按时间范围查询（保留签名，转为本地点日期范围暂不支持，返回全部由调用方过滤）
export async function listLogsByDateRange(start: Date, end: Date): Promise<OperationLog[]> {
  // 后端无按日期范围查询的专用端点，返回全部日志由调用方过滤
  const all = await listLogs({ limit: 1000 });
  const s = start.getTime();
  const e = end.getTime();
  return all.filter((l) => {
    const t = new Date(l.created_at).getTime();
    return t >= s && t <= e;
  });
}
