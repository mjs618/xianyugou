// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReplyAssistantPage from '@/pages/reply-assistant/ReplyAssistantPage';

const replyApi = vi.hoisted(() => ({
  getReplyAssistantSettings: vi.fn(),
  updateReplyAssistantSettings: vi.fn(),
  listReplyRules: vi.fn(),
  createReplyRule: vi.fn(),
  updateReplyRule: vi.fn(),
  deleteReplyRule: vi.fn(),
  generateReplySuggestion: vi.fn(),
}));
const accountApi = vi.hoisted(() => ({ listAccounts: vi.fn() }));
const productApi = vi.hoisted(() => ({ listActiveTemplates: vi.fn() }));

vi.mock('@/services/replyAssistantService', () => replyApi);
vi.mock('@/services/xianyuService', () => accountApi);
vi.mock('@/services/productTemplateService', () => productApi);


describe('ReplyAssistantPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    replyApi.getReplyAssistantSettings.mockResolvedValue({
      id: 1,
      enabled: true,
      ai_enabled: false,
      api_base_url: '',
      api_key_configured: false,
      model: '',
      system_prompt: '',
    });
    replyApi.listReplyRules.mockResolvedValue([]);
    accountApi.listAccounts.mockResolvedValue([
      {
        id: 1,
        nickname: '主账号',
        status: 'online',
        auto_sync_enabled: false,
        auto_sync_interval_minutes: 120,
        consecutive_failures: 0,
        created_at: new Date(),
        updated_at: new Date(),
      },
    ]);
    productApi.listActiveTemplates.mockResolvedValue([]);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    const getComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation((element) => getComputedStyle(element));
  });

  afterEach(() => vi.restoreAllMocks());

  it('generates, edits and copies a manual-review rule suggestion', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '请通过闲鱼订单申请售后。',
      source: 'rule',
      matched_rule_id: 2,
      risk_level: 'manual_required',
      risk_reasons: ['退款售后'],
      copy_allowed: true,
    });
    render(<ReplyAssistantPage />);

    const buyerInput = await screen.findByPlaceholderText('粘贴买家的最新消息');
    fireEvent.change(buyerInput, { target: { value: '我想退款' } });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));

    expect(await screen.findByText('人工核对')).toBeTruthy();
    expect(screen.getByText('固定规则')).toBeTruthy();
    expect(replyApi.generateReplySuggestion).toHaveBeenCalledWith({
      account_id: 1,
      buyer_message: '我想退款',
    });

    const candidate = screen.getByRole('textbox', { name: '候选回复' });
    fireEvent.change(candidate, { target: { value: '已核对，请从订单申请售后。' } });
    fireEvent.click(screen.getByRole('button', { name: '复制候选回复' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('已核对，请从订单申请售后。');
    });
  });

  it('shows the settings entry and manual-send boundary', async () => {
    render(<ReplyAssistantPage />);

    expect(await screen.findByRole('button', { name: '配置回复助手' })).toBeTruthy();
    expect(screen.getByText(/只生成候选，不会自动发送/)).toBeTruthy();
  });

  it('keeps the configured api key blank in the settings drawer', async () => {
    replyApi.getReplyAssistantSettings.mockResolvedValue({
      id: 1,
      enabled: true,
      ai_enabled: true,
      api_base_url: 'https://model.example/v1',
      api_key_configured: true,
      model: 'test-model',
      system_prompt: '',
    });
    render(<ReplyAssistantPage />);

    fireEvent.click(await screen.findByRole('button', { name: '配置回复助手' }));

    expect(await screen.findByText(/已配置；留空保持原密钥不变/)).toBeTruthy();
    expect((screen.getByLabelText('API Key') as HTMLInputElement).value).toBe('');
  });
});
