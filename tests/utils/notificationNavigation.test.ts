import { describe, expect, it } from 'vitest';
import { getNotificationTarget } from '@/utils/notificationNavigation';
import type { NotificationRecord } from '@/types';

const notification = (overrides: Partial<NotificationRecord>): NotificationRecord => ({
  id: 1,
  type: 'aftersales_pending',
  ref_id: 7,
  title: '售后跟进提醒',
  content: '工单超时',
  status: 'unread',
  scheduled_at: new Date('2026-07-09T12:00:00'),
  sent_at: new Date('2026-07-09T12:00:00'),
  created_at: new Date('2026-07-09T12:00:00'),
  ...overrides,
});

describe('notificationNavigation', () => {
  it('售后提醒带工单 ID 时应跳转到售后页并携带 ticketId', () => {
    expect(getNotificationTarget(notification({ ref_id: 7 }))).toBe('/after-sales?ticketId=7');
  });

  it('售后提醒没有工单 ID 时仍跳转售后页', () => {
    expect(getNotificationTarget(notification({ ref_id: undefined }))).toBe('/after-sales');
  });
});
