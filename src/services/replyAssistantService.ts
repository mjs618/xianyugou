import type {
  ReplyAssistantSettings,
  ReplyAssistantSettingsUpdate,
  ReplyRiskCheck,
  ReplyRule,
  ReplyRuleInput,
  ReplySuggestion,
  ReplySuggestionInput,
} from '@/types';
import { apiClient } from './apiClient';


function normalizeRule(rule: Omit<ReplyRule, 'created_at' | 'updated_at'> & {
  created_at: string | Date;
  updated_at: string | Date;
}): ReplyRule {
  return {
    ...rule,
    created_at: new Date(rule.created_at),
    updated_at: new Date(rule.updated_at),
  };
}

export async function getReplyAssistantSettings(): Promise<ReplyAssistantSettings> {
  return apiClient.get<ReplyAssistantSettings>('/api/reply-assistant/settings');
}

export async function updateReplyAssistantSettings(
  patch: ReplyAssistantSettingsUpdate,
): Promise<ReplyAssistantSettings> {
  return apiClient.put<ReplyAssistantSettings>('/api/reply-assistant/settings', patch);
}

export async function listReplyRules(): Promise<ReplyRule[]> {
  const rules = await apiClient.get<any[]>('/api/reply-assistant/rules');
  return rules.map(normalizeRule);
}

export async function createReplyRule(input: ReplyRuleInput): Promise<ReplyRule> {
  const rule = await apiClient.post<any>('/api/reply-assistant/rules', input);
  return normalizeRule(rule);
}

export async function updateReplyRule(
  id: number,
  patch: Partial<ReplyRuleInput>,
): Promise<ReplyRule> {
  const rule = await apiClient.patch<any>(`/api/reply-assistant/rules/${id}`, patch);
  return normalizeRule(rule);
}

export async function deleteReplyRule(id: number): Promise<void> {
  await apiClient.delete(`/api/reply-assistant/rules/${id}`);
}

export async function generateReplySuggestion(
  input: ReplySuggestionInput,
): Promise<ReplySuggestion> {
  return apiClient.postLong<ReplySuggestion>('/api/reply-assistant/suggestions', input);
}

export async function checkReplyRisk(text: string): Promise<ReplyRiskCheck> {
  return apiClient.post<ReplyRiskCheck>('/api/reply-assistant/risk-check', { text });
}
