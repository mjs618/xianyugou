import type { Transaction, WarrantyStatus, WarrantyStatusType } from '@/types';
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

export function canManageWarranty(transaction: Transaction): boolean {
  return transaction.status === 'completed' && transaction.warranty_days > 0 && Boolean(transaction.warranty_end);
}

export function getWarrantyStartLabel(transaction: Transaction, formatDateTime: (date: Date) => string): string {
  if (transaction.warranty_days <= 0) return '不质保';
  if (!transaction.shipped_at) return '发货后起算';
  return formatDateTime(transaction.shipped_at);
}

export function getWarrantyDaysLabel(days: number): string {
  return days > 0 ? `${days} 天` : '不质保';
}

export function getWarrantyFormDefaults(defaultWarrantyDays: number): { hasWarranty: boolean; warrantyDays: number } {
  const warrantyDays = Math.max(0, defaultWarrantyDays);
  return { hasWarranty: warrantyDays > 0, warrantyDays };
}

export function getEnabledWarrantyDays(currentDays: number, defaultWarrantyDays: number): number {
  if (currentDays > 0) return currentDays;
  if (defaultWarrantyDays > 0) return defaultWarrantyDays;
  return 30;
}
