// 邮件发送记录服务 - 数据层迁移最后一批：走后端 API。
// 敏感字段（gpt_password/email_password）由后端加密存储、API 返回明文。
// 前端不再做加解密。
import type { MailRecord } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化
function normalizeRecord(r: any): MailRecord {
  return { ...r, sent_at: new Date(r.sent_at) };
}

// 新增发送记录（后端加密敏感字段）
export async function addMailRecord(record: Omit<MailRecord, 'id'>): Promise<number> {
  const r = await apiClient.post<{ id: number }>('/api/mail-records', record);
  return r.id;
}

// 查询所有发送记录（后端解密敏感字段，返回明文）
export async function listMailRecords(): Promise<MailRecord[]> {
  const list = await apiClient.get<any[]>('/api/mail-records');
  return list.map(normalizeRecord);
}

// 删除单条记录
export async function deleteMailRecord(id: number): Promise<void> {
  await apiClient.delete(`/api/mail-records/${id}`);
}

// 清空所有记录
export async function clearMailRecords(): Promise<void> {
  await apiClient.delete('/api/mail-records');
}
