// 通知服务 - 数据层迁移第三批。
//
// 分工：
// - 通知 CRUD + 待办汇总：走后端 API
// - 提醒生成（质保/回访/返利）：调后端 /reminders/check，后端负责查询+防重+写入
// - 浏览器通知权限/弹窗：留前端（new Notification 是浏览器能力）
import type { NotificationRecord, PendingSummary } from '@/types';
import { apiClient } from './apiClient';

// 日期归一化
function toDate(v: unknown): Date | undefined {
  if (!v) return undefined;
  return new Date(v as string);
}

function normalizeNotification(n: any): NotificationRecord {
  return {
    ...n,
    scheduled_at: new Date(n.scheduled_at),
    sent_at: toDate(n.sent_at),
    created_at: new Date(n.created_at),
  };
}

// 浏览器通知弹窗（私有 helper）
function _showBrowserNotification(title: string, body: string): void {
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    try {
      new Notification(title, { body });
    } catch {
      // 忽略通知异常
    }
  }
}

// 执行所有提醒检查：调后端生成提醒，并对新生成的提醒弹浏览器通知
export async function runAllReminderChecks(): Promise<void> {
  const r = await apiClient.post<{ created: any[] }>('/api/notifications/reminders/check');
  // 对后端新生成的通知弹浏览器通知
  for (const n of r.created || []) {
    _showBrowserNotification(n.title || '提醒', n.content || '');
  }
}

// 获取未读通知数
export async function getUnreadCount(): Promise<number> {
  const r = await apiClient.get<{ count: number }>('/api/notifications/unread-count');
  return r.count;
}

// 获取通知列表
export async function listNotifications(limit = 50): Promise<NotificationRecord[]> {
  const list = await apiClient.get<any[]>('/api/notifications', { limit });
  return list.map(normalizeNotification);
}

// 标记已读
export async function markAsRead(id: number): Promise<void> {
  await apiClient.post(`/api/notifications/${id}/read`);
}

// 全部标记已读
export async function markAllAsRead(): Promise<void> {
  await apiClient.post('/api/notifications/read-all');
}

// 忽略通知
export async function dismiss(id: number): Promise<void> {
  await apiClient.post(`/api/notifications/${id}/dismiss`);
}

// 生成待处理事项汇总
export async function getPendingSummary(): Promise<PendingSummary> {
  return apiClient.get('/api/notifications/pending-summary');
}

// 请求浏览器通知权限（浏览器能力，留前端）
export async function requestNotificationPermission(): Promise<boolean> {
  if (typeof Notification === 'undefined') return false;
  if (Notification.permission === 'granted') return true;
  if (Notification.permission === 'denied') return false;
  const result = await Notification.requestPermission();
  return result === 'granted';
}

// 获取浏览器通知权限状态（浏览器能力，留前端）
export function getNotificationPermission(): 'default' | 'granted' | 'denied' | 'unsupported' {
  if (typeof Notification === 'undefined') return 'unsupported';
  return Notification.permission;
}
