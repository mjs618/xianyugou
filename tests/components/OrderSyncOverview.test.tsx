// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import OrderSyncOverview from '@/pages/ordersync/OrderSyncOverview';
import type { CookieCloudConfigStatus, XianyuAccount } from '@/types';

function account(overrides: Partial<XianyuAccount>): XianyuAccount {
  return {
    id: 1,
    nickname: '测试账号',
    status: 'online',
    auto_sync_enabled: false,
    auto_sync_interval_minutes: 60,
    consecutive_failures: 0,
    created_at: new Date('2026-07-01T00:00:00Z'),
    updated_at: new Date('2026-07-01T00:00:00Z'),
    ...overrides,
  };
}

const cookieCloudDisabled: CookieCloudConfigStatus = {
  enabled: false,
  configured_keys: [],
  missing_keys: ['COOKIE_CLOUD_HOST', 'COOKIE_CLOUD_UUID'],
  domain_keyword: 'goofish.com',
  message: 'CookieCloud 未配置完整',
  next_step: '请在环境变量中完成配置',
};

describe('OrderSyncOverview', () => {
  it('优先展示总览、熔断恢复路径和 CookieCloud 任务', () => {
    render(
      <OrderSyncOverview
        accounts={[
          account({ id: 1, nickname: '0618', status: 'paused', auto_sync_enabled: true }),
          account({ id: 2, nickname: '6674', status: 'paused' }),
          account({ id: 3, nickname: '主号', status: 'paused' }),
        ]}
        cookieCloudStatus={cookieCloudDisabled}
        onReloadCookieCloud={vi.fn()}
      />,
    );

    expect(screen.getByRole('region', { name: '同步状态总览' })).toBeTruthy();
    expect(screen.getByText('全部账号')).toBeTruthy();
    expect(screen.getByText('待处理')).toBeTruthy();
    expect(screen.getByText('自动同步')).toBeTruthy();
    expect(screen.getByText('3 个账号需要处理')).toBeTruthy();
    expect(screen.getByText('0618、6674、主号')).toBeTruthy();
    expect(screen.getByText('更新 Cookie')).toBeTruthy();
    expect(screen.getByText('校验')).toBeTruthy();
    expect(screen.getByText('恢复')).toBeTruthy();
    expect(screen.getByText('CookieCloud 未启用')).toBeTruthy();
    expect(screen.getByRole('button', { name: '重新检测 CookieCloud' })).toBeTruthy();

    const help = screen.getByRole('button', { name: /同步说明与 Cookie 获取方法/ });
    expect(help.getAttribute('aria-expanded')).toBe('false');
  });

  it('服务状态未知时不误报 CookieCloud 告警', () => {
    render(
      <OrderSyncOverview
        accounts={[]}
        cookieCloudStatus={null}
        onReloadCookieCloud={vi.fn()}
      />,
    );

    expect(screen.getByText('状态未知')).toBeTruthy();
    expect(screen.queryByText('CookieCloud 未启用')).toBeNull();
    expect(screen.queryByText(/个账号需要处理/)).toBeNull();
  });
});
