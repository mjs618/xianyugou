import { Badge } from 'antd';
import { createElement, type ReactNode } from 'react';
import type { PendingSummary } from '@/types';
import { getNavigationBadgeCount } from '@/utils/navigationBadges';

export interface LayoutNavigationItem {
  key: string;
  icon: ReactNode;
  label: string;
}

export const LAYOUT_NAVIGATION_ROUTES = [
  { key: '/', label: '首页' },
  { key: '/transactions', label: '交易管理' },
  { key: '/customers', label: '客户管理' },
  { key: '/referral', label: '推荐链' },
  { key: '/warranty', label: '质保监控' },
  { key: '/after-sales', label: '售后管理' },
  { key: '/finance', label: '财务报表' },
  { key: '/send-mail', label: '发货邮件' },
  { key: '/reply-assistant', label: '回复助手' },
  { key: '/order-sync', label: '订单同步' },
  { key: '/settings', label: '设置' },
] as const;

function renderIconWithBadge(icon: ReactNode, count: number) {
  if (count <= 0) return icon;

  return createElement(
    Badge,
    { count, size: 'small', offset: [2, -2] },
    createElement('span', { style: { display: 'inline-flex' } }, icon),
  );
}

function renderLabelWithBadge(label: string, count: number) {
  return createElement(
    Badge,
    { count, size: 'small', offset: [8, 0] },
    createElement('span', null, label),
  );
}

export function buildLayoutMenuItems(items: LayoutNavigationItem[], collapsed: boolean, pendingSummary: PendingSummary) {
  return items.map((item) => {
    const badgeCount = getNavigationBadgeCount(item.key, pendingSummary);
    return {
      ...item,
      icon: collapsed ? renderIconWithBadge(item.icon, badgeCount) : item.icon,
      label: collapsed ? null : renderLabelWithBadge(item.label, badgeCount),
    };
  });
}
