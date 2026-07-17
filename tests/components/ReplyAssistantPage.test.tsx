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
  checkReplyRisk: vi.fn(),
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
    replyApi.checkReplyRisk.mockResolvedValue({ risk_level: 'normal', risk_reasons: [] });
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

  afterEach(() => {
    vi.restoreAllMocks();
  });

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

  it('submits optional recent context with explicit buyer and seller roles', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '候选',
      source: 'ai',
      matched_rule_id: null,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });
    render(<ReplyAssistantPage />);

    fireEvent.change(await screen.findByPlaceholderText('每行一条，例如：买家：想了解一下'), {
      target: { value: '卖家：您好\n买家：想了解一下' },
    });
    fireEvent.change(screen.getByPlaceholderText('粘贴买家的最新消息'), {
      target: { value: '还有货吗？' },
    });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));

    await waitFor(() => expect(replyApi.generateReplySuggestion).toHaveBeenCalledWith({
      account_id: 1,
      buyer_message: '还有货吗？',
      context_messages: [
        { role: 'seller', content: '您好' },
        { role: 'user', content: '想了解一下' },
      ],
    }));
  });

  it('clears a stale candidate when the input changes', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '旧候选',
      source: 'rule',
      matched_rule_id: 1,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });
    render(<ReplyAssistantPage />);

    const input = await screen.findByPlaceholderText('粘贴买家的最新消息');
    fireEvent.change(input, { target: { value: '第一条消息' } });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));
    expect(await screen.findByRole('textbox', { name: '候选回复' })).toBeTruthy();

    fireEvent.change(input, { target: { value: '另一条消息' } });

    expect(screen.queryByRole('textbox', { name: '候选回复' })).toBeNull();
    expect((input as HTMLTextAreaElement).value).toBe('另一条消息');
  });

  it('shows a retry action when initial loading fails', async () => {
    replyApi.getReplyAssistantSettings
      .mockRejectedValueOnce(new Error('加载失败'))
      .mockResolvedValueOnce({
        id: 1,
        enabled: true,
        ai_enabled: false,
        api_base_url: '',
        api_key_configured: false,
        model: '',
        system_prompt: '',
      });
    render(<ReplyAssistantPage />);

    fireEvent.click(await screen.findByRole('button', { name: '重新加载' }));

    expect(await screen.findByRole('heading', { name: '闲鱼回复助手' })).toBeTruthy();
  });

  it('blocks copy and asks for confirmation when edited candidate is risky', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '已编辑内容',
      source: 'ai',
      matched_rule_id: null,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });
    replyApi.checkReplyRisk.mockResolvedValueOnce({
      risk_level: 'manual_required',
      risk_reasons: ['隐私认证'],
    });
    render(<ReplyAssistantPage />);

    fireEvent.change(await screen.findByPlaceholderText('粘贴买家的最新消息'), {
      target: { value: '你好' },
    });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));
    const candidate = await screen.findByRole('textbox', { name: '候选回复' });
    fireEvent.change(candidate, { target: { value: '请把电话发我' } });
    fireEvent.click(screen.getByRole('button', { name: '复制候选回复' }));

    const confirmButton = await screen.findByRole('button', { name: '已核对，继续复制' });
    expect(screen.getByText(/隐私认证/)).toBeTruthy();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();

    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('请把电话发我');
    });
  });

  it('does not copy when risk confirmation is cancelled', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '请把电话发我',
      source: 'ai',
      matched_rule_id: null,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });
    replyApi.checkReplyRisk.mockResolvedValueOnce({
      risk_level: 'manual_required',
      risk_reasons: ['隐私认证'],
    });
    render(<ReplyAssistantPage />);

    fireEvent.change(await screen.findByPlaceholderText('粘贴买家的最新消息'), {
      target: { value: '你好' },
    });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));
    await screen.findByRole('textbox', { name: '候选回复' });
    fireEvent.click(screen.getByRole('button', { name: '复制候选回复' }));

    const cancelButton = await screen.findByRole('button', { name: '取消复制' });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    });
  });

  it('does not copy and shows error when risk check fails', async () => {
    replyApi.generateReplySuggestion.mockResolvedValue({
      reply: '候选',
      source: 'ai',
      matched_rule_id: null,
      risk_level: 'normal',
      risk_reasons: [],
      copy_allowed: true,
    });
    replyApi.checkReplyRisk.mockRejectedValueOnce(new Error('网络错误'));
    render(<ReplyAssistantPage />);

    fireEvent.change(await screen.findByPlaceholderText('粘贴买家的最新消息'), {
      target: { value: '你好' },
    });
    fireEvent.click(screen.getByRole('button', { name: '生成候选回复' }));
    await screen.findByRole('textbox', { name: '候选回复' });
    fireEvent.click(screen.getByRole('button', { name: '复制候选回复' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    });
  });
});
