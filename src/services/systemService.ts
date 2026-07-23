// 系统管理服务：服务器备份列表与数据库恢复（E6 新增）。
//
// 与 BackupRestoreTab 的 JSON 导入恢复（应用层数据）互补：
// 这是文件级灾难恢复 —— 从后端 data/backups/daily/*.db 整库恢复。
//
// 恢复是不可逆操作：会覆盖当前数据库。后端限流 3 次/分钟，且要求 confirm=true 二次确认。
import { apiClient } from './apiClient';

/** 一个可用服务器备份文件的元信息（对应后端 BackupInfo schema）。 */
export interface ServerBackupInfo {
  /** 备份文件名，如 xianyu-20260714-120000.db */
  filename: string;
  /** 备份文件大小（字节） */
  size_bytes: number;
  /** 备份创建时间（UTC ISO 格式） */
  created_at: string;
  /** 备份内各表行数（从 manifest 读取，无 manifest 则为空） */
  table_counts: Record<string, number>;
  /** manifest 中记录的 integrity_check 是否为 ok */
  integrity_ok: boolean;
}

/** GET /api/system/backups 响应。 */
export interface BackupListResponse {
  backups: ServerBackupInfo[];
  /** 备份目录绝对路径（用于排查） */
  backup_dir: string;
}

/** POST /api/system/restore 响应：恢复结果报告。 */
export interface RestoreResponse {
  success: boolean;
  message: string;
  /** 恢复前自动备份的旧数据库路径（回退用） */
  pre_restore_path?: string;
  integrity_check?: string;
  table_counts?: Record<string, number>;
}

/** 列出可用的服务器备份文件。 */
export async function listServerBackups(): Promise<BackupListResponse> {
  return apiClient.get<BackupListResponse>('/api/system/backups');
}

/**
 * 从服务器备份文件恢复数据库（不可逆，覆盖当前数据）。
 *
 * 用 postLong：恢复可能耗时（SQLite backup API 整库复制），
 * 且关闭重试避免重复执行不可逆操作。
 */
export async function restoreServerBackup(filename: string): Promise<RestoreResponse> {
  return apiClient.postLong<RestoreResponse>('/api/system/restore', {
    filename,
    confirm: true, // 后端要求二次确认
  });
}
