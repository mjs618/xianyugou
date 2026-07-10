import { FileTextOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Badge } from 'antd';
import { Children, createElement, isValidElement, type ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { buildLayoutMenuItems, type LayoutNavigationItem } from '@/utils/layoutNavigation';

const menuItems: LayoutNavigationItem[] = [
  { key: '/transactions', icon: createElement(FileTextOutlined), label: '交易管理' },
  { key: '/warranty', icon: createElement(SafetyCertificateOutlined), label: '质保监控' },
];

const pendingSummary = {
  warrantyUrgent: 2,
  afterSalesPending: 0,
  rebatePending: 0,
};

function getBadgeCounts(node: ReactNode): number[] {
  if (!isValidElement(node)) return [];

  const ownCounts = node.type === Badge ? [Number(node.props.count)] : [];
  const childCounts = Children.toArray(node.props.children).flatMap(getBadgeCounts);
  return [...ownCounts, ...childCounts];
}

describe('layoutNavigation', () => {
  it('折叠侧栏时把待办徽标显示在菜单图标上', () => {
    const items = buildLayoutMenuItems(menuItems, true, pendingSummary);
    const warrantyItem = items.find((item) => item?.key === '/warranty');
    const transactionItem = items.find((item) => item?.key === '/transactions');

    expect(warrantyItem?.label).toBeNull();
    expect(getBadgeCounts(warrantyItem?.icon)).toEqual([2]);
    expect(getBadgeCounts(transactionItem?.icon)).toEqual([]);
  });

  it('展开侧栏时仍把待办徽标显示在菜单文字上', () => {
    const items = buildLayoutMenuItems(menuItems, false, pendingSummary);
    const warrantyItem = items.find((item) => item?.key === '/warranty');

    expect(getBadgeCounts(warrantyItem?.icon)).toEqual([]);
    expect(getBadgeCounts(warrantyItem?.label)).toEqual([2]);
  });
});
