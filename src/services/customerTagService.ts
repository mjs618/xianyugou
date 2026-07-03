// 客户标签服务 - 数据层迁移第四批：走后端 API。
// 标签 CRUD + setCustomerTags 级联（自动建标签/重建关联）由后端完成。
import type { CustomerTag } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化
function normalizeTag(t: any): CustomerTag {
  return {
    ...t,
    created_at: new Date(t.created_at),
  };
}

// 获取所有标签定义
export async function listTags(): Promise<CustomerTag[]> {
  const list = await apiClient.get<any[]>('/api/customer-tags');
  return list.map(normalizeTag);
}

// 创建标签
export async function createTag(name: string, color?: string): Promise<CustomerTag> {
  const t = await apiClient.post<any>('/api/customer-tags', { name, color });
  return normalizeTag(t);
}

// 删除标签（后端级联清理客户 tags 字段与关联表）
export async function deleteTag(id: number): Promise<void> {
  await apiClient.delete(`/api/customer-tags/${id}`);
}

// 获取客户的标签列表
export async function getCustomerTags(customerId: number): Promise<CustomerTag[]> {
  const list = await apiClient.get<any[]>(`/api/customer-tags/by-customer/${customerId}`);
  return list.map(normalizeTag);
}

// 为客户设置标签（后端自动建标签 + 更新客户 tags + 重建关联）
export async function setCustomerTags(customerId: number, tagNames: string[]): Promise<void> {
  await apiClient.post(`/api/customer-tags/set-customer/${customerId}`, { tags: tagNames });
}
