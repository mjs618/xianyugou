import type { OperatingExpense } from '@/types';
import { apiClient } from './apiClient';

function normalizeExpense(raw: any): OperatingExpense {
  return {
    ...raw,
    occurred_at: new Date(raw.occurred_at),
    created_at: new Date(raw.created_at),
    updated_at: new Date(raw.updated_at),
  };
}

export async function listExpenses(start?: Date, end?: Date): Promise<OperatingExpense[]> {
  const params: Record<string, string> = {};
  if (start && end) {
    params.start = start.toISOString();
    params.end = end.toISOString();
  }
  const rows = await apiClient.get<any[]>('/api/expenses', params);
  return rows.map(normalizeExpense);
}

export async function createExpense(input: {
  category: string;
  amount: number;
  occurred_at: Date;
  notes?: string;
}): Promise<OperatingExpense> {
  const row = await apiClient.post<any>('/api/expenses', {
    ...input,
    occurred_at: input.occurred_at.toISOString(),
  });
  return normalizeExpense(row);
}

export async function updateExpense(id: number, patch: Partial<{
  category: string;
  amount: number;
  occurred_at: Date;
  notes?: string;
}>): Promise<OperatingExpense> {
  const body = {
    ...patch,
    occurred_at: patch.occurred_at?.toISOString(),
  };
  const row = await apiClient.patch<any>(`/api/expenses/${id}`, body);
  return normalizeExpense(row);
}

export async function deleteExpense(id: number): Promise<void> {
  await apiClient.delete(`/api/expenses/${id}`);
}
