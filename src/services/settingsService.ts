// 系统设置服务 - 调用后端 API（后端统一加密存储 smtp_pass，自动级联重算）。
//
// 切换说明（数据层迁移第一批）：
// - getSettings/updateSettings 改为调用后端 /api/settings
// - 加解密移到后端：前端不再 encryptField/decryptField，API 返回明文 smtp_pass
// - 级联重算（recalcAllCustomersStats / recalcPendingRebates）由后端在 updateSettings 时自动触发
// - migrateEncryptSettings 删除（后端启动时自动迁移存量明文）
import { apiClient, ApiException } from './apiClient';
import { DEFAULT_SETTINGS, type Settings } from '@/types';

// 获取设置（单例，id=1）—— 返回明文（后端已解密 smtp_pass）
export async function getSettings(): Promise<Settings> {
  try {
    return await apiClient.get<Settings>('/api/settings');
  } catch (err) {
    // 后端不可用时回退默认设置（避免阻塞应用启动）
    console.warn('获取设置失败，使用默认值:', err);
    return { ...DEFAULT_SETTINGS };
  }
}

// 更新设置 —— 后端校验 + 加密 + 触发级联重算（客户等级/返利金额）
export async function updateSettings(patch: Partial<Settings>): Promise<Settings> {
  return apiClient.put<Settings>('/api/settings', patch);
}

// 保留空函数签名兼容旧调用点（main.tsx 启动迁移已移除，后端自管加密）
export async function migrateEncryptSettings(): Promise<void> {
  // no-op：加密由后端在数据写入时自动处理
  return;
}
