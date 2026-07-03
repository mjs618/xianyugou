import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  getUnreadCount,
  listNotifications,
  markAsRead,
  markAllAsRead,
  dismiss,
  getPendingSummary,
  runAllReminderChecks,
  requestNotificationPermission,
  getNotificationPermission,
} from '@/services/notificationService';

const NOTIF = (over: any = {}) => ({
  id: 1, type: 'warranty_expiring', ref_id: 5, title: '质保到期提醒',
  content: '即将过保', status: 'unread',
  scheduled_at: '2026-06-30T00:00:00', sent_at: '2026-06-30T00:00:00', created_at: '2026-06-30T00:00:00',
  ...over,
});

describe('notificationService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('getUnreadCount 应 GET /api/notifications/unread-count', async () => {
    setMockResponse('get', '/api/notifications/unread-count', { count: 3 });
    expect(await getUnreadCount()).toBe(3);
  });

  it('listNotifications 应 GET 并转换日期', async () => {
    setMockResponse('get', '/api/notifications', [NOTIF()]);
    const list = await listNotifications(20);
    expect(list[0].created_at).toBeInstanceOf(Date);
    expect(list[0].scheduled_at).toBeInstanceOf(Date);
  });

  it('markAsRead 应 POST /{id}/read', async () => {
    setMockResponse('post', '/api/notifications/1/read', { ok: true });
    await markAsRead(1);
    expect(getMockCalls('post', '/api/notifications/1/read').length).toBe(1);
  });

  it('markAllAsRead 应 POST /read-all', async () => {
    setMockResponse('post', '/api/notifications/read-all', { ok: true });
    await markAllAsRead();
    expect(getMockCalls('post', '/api/notifications/read-all').length).toBe(1);
  });

  it('dismiss 应 POST /{id}/dismiss', async () => {
    setMockResponse('post', '/api/notifications/1/dismiss', { ok: true });
    await dismiss(1);
    expect(getMockCalls('post', '/api/notifications/1/dismiss').length).toBe(1);
  });

  it('getPendingSummary 应 GET /api/notifications/pending-summary', async () => {
    setMockResponse('get', '/api/notifications/pending-summary', {
      warrantyUrgent: 2, afterSalesPending: 1, rebatePending: 3,
    });
    const s = await getPendingSummary();
    expect(s.warrantyUrgent).toBe(2);
    expect(s.rebatePending).toBe(3);
  });

  it('runAllReminderChecks 应 POST /reminders/check', async () => {
    setMockResponse('post', '/api/notifications/reminders/check', {
      created: [NOTIF({ id: 10, title: '质保提醒', content: '即将过保' })],
    });
    await runAllReminderChecks();
    expect(getMockCalls('post', '/api/notifications/reminders/check').length).toBe(1);
  });

  it('getNotificationPermission 浏览器能力（无 Notification 环境返回 unsupported）', () => {
    // node 测试环境无 Notification
    expect(getNotificationPermission()).toBe('unsupported');
  });

  it('requestNotificationPermission 无 Notification 环境返回 false', async () => {
    expect(await requestNotificationPermission()).toBe(false);
  });
});
