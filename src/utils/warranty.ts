import type { WarrantyStatus, WarrantyStatusType } from '@/types';
import { daysBetween } from './date';

// 质保状态计算（BR-2 相关展示）
export function getWarrantyStatus(warrantyEnd?: Date | string | null): WarrantyStatus {
  if (!warrantyEnd) {
    return { type: 'none', label: '无质保', color: 'default', daysLeft: 0 };
  }
  const daysLeft = daysBetween(new Date(warrantyEnd));
  if (daysLeft <= 0) {
    return { type: 'expired', label: '已过期', color: 'gray', daysLeft: 0 };
  }
  if (daysLeft <= 3) {
    return { type: 'urgent', label: `剩${daysLeft}天`, color: 'red', daysLeft };
  }
  return { type: 'active', label: `剩${daysLeft}天`, color: 'green', daysLeft };
}

// 质保状态颜色映射（antd Tag color）
export const warrantyTagColor = (type: WarrantyStatusType): string => {
  switch (type) {
    case 'active':
      return 'green';
    case 'urgent':
      return 'red';
    case 'expired':
      return 'default';
    default:
      return 'default';
  }
};

// 计算质保到期时间 = 完成时间 + 质保天数
export function calcWarrantyEnd(completedAt: Date, days: number): Date {
  const end = new Date(completedAt);
  end.setDate(end.getDate() + days);
  return end;
}
