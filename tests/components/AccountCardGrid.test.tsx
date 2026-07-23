// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AccountCardGrid from '@/pages/ordersync/AccountCardGrid';
import type { XianyuAccount } from '@/types';

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

function props(accounts: XianyuAccount[]) {
  return {
    accounts,
    loading: false,
    syncingId: null,
    onSync: vi.fn(),
    itemSyncingId: null,
    onSyncItems: vi.fn(),
    onTest: vi.fn(),
    onOpenOrderMirror: vi.fn(),
    onOpenItemMirror: vi.fn(),
    onOpenSyncLog: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    togglingId: null,
    editingInterval: {},
    onToggleAutoSync: vi.fn(),
    onCommitInterval: vi.fn(),
    onEditInterval: vi.fn(),
    recoveringId: null,
    onRecover: vi.fn(),
    onAddAccount: vi.fn(),
  };
}

describe('AccountCardGrid', () => {
  it('按账号状态展示主操作，并把次要操作收进更多菜单', async () => {
    render(
      <AccountCardGrid
        {...props([
          account({ id: 1, nickname: '0618', status: 'paused', last_error: 'Cookie 已过期' }),
          account({ id: 2, nickname: '正常账号', status: 'online', auto_sync_enabled: true }),
        ])}
      />,
    );

    expect(screen.getByRole('button', { name: '更新 Cookie 0618' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '校验并恢复 0618' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '同步订单 正常账号' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '同步商品 正常账号' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '更多操作 正常账号' }));
    expect(await screen.findByText('订单镜像')).toBeTruthy();
    expect(screen.getByText('商品镜像')).toBeTruthy();
    expect(screen.getByText('同步日志')).toBeTruthy();
    expect(screen.getByText('删除账号')).toBeTruthy();
  });

  it('空列表提供明确的添加账号入口', () => {
    const emptyProps = props([]);
    render(<AccountCardGrid {...emptyProps} />);

    expect(screen.getByText('还没有闲鱼账号')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '添加第一个账号' }));
    expect(emptyProps.onAddAccount).toHaveBeenCalledTimes(1);
  });
});
