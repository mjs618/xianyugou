import { Badge } from 'antd';
import { createElement, type ReactNode } from 'react';
import type { PendingSummary } from '@/types';
import { getNavigationBadgeCount } from '@/utils/navigationBadges';

export interface LayoutNavigationItem {
  key: string;
  icon: ReactNode;
  label: string;
}

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
