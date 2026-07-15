// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getTokenStatus: vi.fn(),
  verifyToken: vi.fn(),
  getApiToken: vi.fn(),
  setApiToken: vi.fn(),
  subscribeAuthRequired: vi.fn(),
  authRequiredListener: undefined as (() => void) | undefined,
}));

vi.mock('@/services/authService', () => ({
  getTokenStatus: mocks.getTokenStatus,
  verifyToken: mocks.verifyToken,
}));

vi.mock('@/services/apiClient', () => ({
  getApiToken: mocks.getApiToken,
  setApiToken: mocks.setApiToken,
  subscribeAuthRequired: mocks.subscribeAuthRequired,
}));

import AuthGate from '@/auth/AuthGate';

describe('AuthGate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.authRequiredListener = undefined;
    mocks.getApiToken.mockReturnValue(null);
    mocks.getTokenStatus.mockResolvedValue({ token_configured: true });
    mocks.verifyToken.mockResolvedValue({ valid: true });
    mocks.subscribeAuthRequired.mockImplementation((listener: () => void) => {
      mocks.authRequiredListener = listener;
      return () => {};
    });
  });

  it('当前会话无 Token 时显示解锁页且不挂载业务内容', async () => {
    render(<AuthGate><div>业务首页</div></AuthGate>);

    expect(await screen.findByText('解锁系统')).toBeTruthy();
    expect(screen.queryByText('业务首页')).toBeNull();
  });

  it('后端不可达时显示重新检测并可恢复到解锁页', async () => {
    mocks.getTokenStatus.mockRejectedValueOnce(new Error('offline'));
    render(<AuthGate><div>业务首页</div></AuthGate>);

    expect(await screen.findByText('后端服务不可达')).toBeTruthy();
    mocks.getTokenStatus.mockResolvedValueOnce({ token_configured: true });
    fireEvent.click(screen.getByRole('button', { name: '重新检测' }));

    expect(await screen.findByText('解锁系统')).toBeTruthy();
  });

  it('Token 校验通过后保存到会话并挂载业务内容', async () => {
    render(<AuthGate><div>业务首页</div></AuthGate>);
    await screen.findByText('解锁系统');

    fireEvent.change(screen.getByLabelText('API Token'), { target: { value: 'valid-token' } });
    fireEvent.click(screen.getByRole('button', { name: '验证并进入' }));

    await waitFor(() => expect(mocks.verifyToken).toHaveBeenCalledWith('valid-token'));
    expect(mocks.setApiToken).toHaveBeenCalledWith('valid-token');
    expect(await screen.findByText('业务首页')).toBeTruthy();
  });

  it('业务请求触发认证失效后立即收回业务内容', async () => {
    mocks.getApiToken.mockReturnValue('current-token');
    render(<AuthGate><div>业务首页</div></AuthGate>);
    expect(await screen.findByText('业务首页')).toBeTruthy();

    act(() => mocks.authRequiredListener?.());

    expect(await screen.findByText('解锁系统')).toBeTruthy();
    expect(screen.queryByText('业务首页')).toBeNull();
  });
});
