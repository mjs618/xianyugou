import type { NotificationRecord } from '@/types';

export function getNotificationTarget(notification: NotificationRecord): string | undefined {
  if (notification.type === 'warranty_expiring') return '/warranty';
  if (notification.type === 'aftersales_pending') {
    return notification.ref_id ? `/after-sales?ticketId=${notification.ref_id}` : '/after-sales';
  }
  if (notification.type === 'rebate_pending') return '/finance';
  if (notification.type === 'customer_recall' && notification.ref_id) return `/customers/${notification.ref_id}`;
  if (notification.type === 'mail_alert') return '/send-mail';
  return undefined;
}
