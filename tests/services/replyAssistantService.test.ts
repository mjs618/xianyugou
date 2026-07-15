import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getMockCalls,
  mockApiFactory,
  resetMockApi,
  setMockResponse,
} from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());

import {
  createReplyRule,
  deleteReplyRule,
  generateReplySuggestion,
  getReplyAssistantSettings,
  listReplyRules,
  updateReplyAssistantSettings,
  updateReplyRule,
} from '@/services/replyAssistantService';


const settingsResponse = {
  id: 1,
  enabled: true,
  ai_enabled: true,
  api_base_url: 'https://model.example/v1',
  api_key_configured: true,
  model: 'test-model',
  system_prompt: '简洁回答',
};

const ruleResponse = {
  id: 2,
  name: '价格规则',
  enabled: true,
  priority: 10,
  keywords: ['价格'],
  reply_text: '页面价格就是当前售价。',
  product_template_id: 3,
  created_at: '2026-07-16T00:00:00Z',
  updated_at: '2026-07-16T01:00:00Z',
};


describe('replyAssistantService', () => {
  beforeEach(() => resetMockApi());

  it('settings read never contains api_key', async () => {
    setMockResponse('get', '/api/reply-assistant/settings', settingsResponse);

    const result = await getReplyAssistantSettings();

    expect(result.api_key_configured).toBe(true);
    expect(result).not.toHaveProperty('api_key');
  });

  it('updates settings with the exact explicit patch', async () => {
    const patch = { enabled: true, api_key: 'new-key', model: 'model-b' };
    setMockResponse('put', '/api/reply-assistant/settings', settingsResponse);

    await updateReplyAssistantSettings(patch);

    expect(getMockCalls('put', '/api/reply-assistant/settings')[0].body).toEqual(patch);
  });

  it('normalizes rule dates and supports CRUD', async () => {
    setMockResponse('get', '/api/reply-assistant/rules', [ruleResponse]);
    setMockResponse('post', '/api/reply-assistant/rules', ruleResponse);
    setMockResponse('patch', '/api/reply-assistant/rules/2', ruleResponse);
    setMockResponse('delete', '/api/reply-assistant/rules/2', { message: '已删除' });

    const rules = await listReplyRules();
    const created = await createReplyRule({
      name: '价格规则',
      keywords: ['价格'],
      reply_text: '页面价格就是当前售价。',
    });
    await updateReplyRule(2, { enabled: false });
    await deleteReplyRule(2);

    expect(rules[0].created_at).toBeInstanceOf(Date);
    expect(created.updated_at).toBeInstanceOf(Date);
    expect(getMockCalls('patch', '/api/reply-assistant/rules/2')[0].body).toEqual({ enabled: false });
    expect(getMockCalls('delete', '/api/reply-assistant/rules/2')).toHaveLength(1);
  });

  it('posts the exact suggestion input', async () => {
    const input = {
      account_id: 1,
      product_template_id: 3,
      buyer_message: '还有货吗？',
      context_messages: [{ role: 'seller' as const, content: '您好' }],
    };
    setMockResponse('postLong', '/api/reply-assistant/suggestions', {
      reply: '可以直接下单。',
      source: 'ai',
      matched_rule_id: null,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });

    const result = await generateReplySuggestion(input);

    expect(result.source).toBe('ai');
    expect(getMockCalls('postLong', '/api/reply-assistant/suggestions')[0].body).toEqual(input);
  });
});
