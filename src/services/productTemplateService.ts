// 商品模板服务 - 数据层迁移最后一批：走后端 API。
import type { ProductTemplate } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化
function normalizeTemplate(t: any): ProductTemplate {
  return {
    ...t,
    created_at: new Date(t.created_at),
    updated_at: new Date(t.updated_at),
  };
}

export async function listTemplates(): Promise<ProductTemplate[]> {
  const list = await apiClient.get<any[]>('/api/product-templates');
  return list.map(normalizeTemplate).sort((a, b) => a.name.localeCompare(b.name));
}

export async function listActiveTemplates(): Promise<ProductTemplate[]> {
  const list = await apiClient.get<any[]>('/api/product-templates', { active_only: true });
  return list.map(normalizeTemplate).sort((a, b) => a.name.localeCompare(b.name));
}

export async function createTemplate(input: {
  name: string;
  default_cost: number;
  default_sale_price?: number;
  category?: string;
  warranty_days?: number;
}): Promise<ProductTemplate> {
  const body = { ...input, warranty_days: input.warranty_days ?? 30, is_active: true };
  const t = await apiClient.post<any>('/api/product-templates', body);
  return normalizeTemplate(t);
}

export async function updateTemplate(id: number, patch: Partial<ProductTemplate>): Promise<void> {
  await apiClient.patch(`/api/product-templates/${id}`, patch);
}

export async function deleteTemplate(id: number): Promise<void> {
  await apiClient.delete(`/api/product-templates/${id}`);
}

export async function toggleActive(id: number): Promise<void> {
  await apiClient.post(`/api/product-templates/${id}/toggle`);
}
