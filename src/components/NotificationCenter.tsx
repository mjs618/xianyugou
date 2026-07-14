import { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Button, Dropdown, Empty, List } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  BellOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  GiftOutlined,
  UserSwitchOutlined,
  MailOutlined,
  WarningOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { listNotifications, markAllAsRead, markAsRead } from '@/services/notificationService';
import { useAppStore } from '@/store/useAppStore';
import { formatDate } from '@/utils/date';
import { getNotificationTarget } from '@/utils/notificationNavigation';
import type { NotificationRecord } from '@/types';

// 通知类型 -> 图标 + 颜色映射
const notifTypeMap: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  warranty_expiring: { icon: <SafetyCertificateOutlined />, color: 'var(--color-danger)', bg: 'var(--color-danger-light)' },
  aftersales_pending: { icon: <ToolOutlined />, color: 'var(--theme-primary)', bg: 'var(--color-warning-light)' },
  rebate_pending: { icon: <GiftOutlined />, color: 'var(--color-success)', bg: 'var(--color-success-light)' },
  customer_recall: { icon: <UserSwitchOutlined />, color: 'var(--color-info)', bg: 'var(--color-info-light)' },
  mail_alert: { icon: <MailOutlined />, color: 'var(--color-danger)', bg: 'var(--color-danger-light)' },
  account_paused: { icon: <WarningOutlined />, color: 'var(--color-danger)', bg: 'var(--color-danger-light)' },
  account_recovered: { icon: <CheckCircleOutlined />, color: 'var(--color-success)', bg: 'var(--color-success-light)' },
};

// P1-5 修复：轮询退避常量与计算函数抽到 utils，便于单测（无 JSX 依赖）
import {
  BASE_INTERVAL as POLLING_BASE_INTERVAL,
  MIN_INTERVAL as POLLING_MIN_INTERVAL,
  computeNextInterval,
} from '@/utils/notificationPolling';

export default function NotificationCenter({ isMobile }: { isMobile: boolean }) {
  const navigate = useNavigate();
  const { unreadCount, refreshAll, loadNotifications: refreshBadgeCount } = useAppStore();
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);

  const loadNotifications = useCallback(async () => {
    const list = await listNotifications(20);
    setNotifications(list);
  }, []);

  const handleNotifClick = async (n: NotificationRecord) => {
    await markAsRead(n.id!);
    setNotifOpen(false);
    refreshAll();
    loadNotifications();
    const target = getNotificationTarget(n);
    if (target) navigate(target);
  };

  // P1-5 修复：通知轮询指数退避
  // - 面板打开或上次有未读：30s 快速刷新
  // - 面板关闭且无未读：60s → 90s → 135s → 202s → 300s 缓步退避
  // - 请求失败：每次退避翻倍，封顶 300s
  // - 状态变更（打开/关闭面板）：立即触发一次刷新并重置退避
  // - 标记已读由 handleNotifClick 手动触发刷新，下次 tick 时根据最新 unreadCount 调整间隔
  // 用 ref 同步最新状态，避免 unreadCount 变化频繁重启 effect
  const unreadCountRef = useRef(unreadCount);
  const notifOpenRef = useRef(notifOpen);
  useEffect(() => { unreadCountRef.current = unreadCount; }, [unreadCount]);
  useEffect(() => { notifOpenRef.current = notifOpen; }, [notifOpen]);

  // 当前轮询间隔（ref 让递归 tick 能读取/更新最新值）
  const currentIntervalRef = useRef<number>(POLLING_BASE_INTERVAL);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;

    // 状态变更（打开/关闭面板）时重置为快速间隔，立即触发一次刷新
    currentIntervalRef.current = notifOpen ? POLLING_MIN_INTERVAL : POLLING_BASE_INTERVAL;

    const tick = async () => {
      if (cancelled) return;
      let failed = false;
      try {
        await refreshBadgeCount();
        if (notifOpenRef.current) {
          await loadNotifications();
        }
      } catch {
        failed = true;
      }
      if (!cancelled) {
        currentIntervalRef.current = computeNextInterval(
          currentIntervalRef.current,
          unreadCountRef.current > 0,
          notifOpenRef.current,
          failed
        );
        timer = setTimeout(tick, currentIntervalRef.current);
      }
    };

    // 状态变化时立即触发一次（延迟 0ms），随后按 currentIntervalRef 递归调度
    timer = setTimeout(tick, 0);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // 仅依赖 notifOpen 触发重启；unreadCount 通过 ref 同步避免频繁重启
    // refreshBadgeCount / loadNotifications 是 zustand 稳定引用，不引起重启
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifOpen, refreshBadgeCount, loadNotifications]);

  const notifContent = (
    <div style={{ width: isMobile ? 300 : 380, background: 'var(--color-surface)', borderRadius: 8, boxShadow: '0 6px 16px rgba(0,0,0,0.08)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--color-border)' }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>通知</span>
        {unreadCount > 0 && (
          <Button type="link" size="small" onClick={async () => { await markAllAsRead(); refreshAll(); loadNotifications(); }}>
            全部已读
          </Button>
        )}
      </div>
      {notifications.length === 0 ? (
        <Empty description="暂无通知" style={{ padding: 32 }} />
      ) : (
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          <List
            size="small"
            dataSource={notifications}
            renderItem={(n) => {
              const typeConfig = notifTypeMap[n.type] || { icon: <BellOutlined />, color: 'var(--theme-primary)', bg: 'var(--theme-primary-bg)' };
              return (
                <List.Item
                  role="button"
                  tabIndex={0}
                  aria-label={`${n.title}，${n.content}`}
                  onClick={() => handleNotifClick(n)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleNotifClick(n);
                    }
                  }}
                  style={{
                    cursor: 'pointer',
                    background: n.status === 'unread' ? 'var(--theme-primary-bg)' : 'transparent',
                    padding: '12px 16px',
                    borderBottom: '1px solid var(--color-border)',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', gap: 12, width: '100%' }}>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        background: typeConfig.bg,
                        color: typeConfig.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        fontSize: 15,
                      }}
                    >
                      {typeConfig.icon}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-dark)' }}>{n.title}</span>
                        {n.status === 'unread' && (
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--theme-primary)', flexShrink: 0 }} />
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
                        {n.content}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
                        {formatDate(n.created_at, 'YYYY-MM-DD HH:mm')}
                      </div>
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
        </div>
      )}
    </div>
  );

  return (
    <Dropdown
      trigger={['click']}
      open={notifOpen}
      onOpenChange={(open) => {
        setNotifOpen(open);
        if (open) loadNotifications();
      }}
      dropdownRender={() => notifContent}
    >
      <Badge count={unreadCount} size="small" offset={[-2, 2]}>
        <Button
          type="text"
          shape="circle"
          size={isMobile ? 'small' : 'middle'}
          icon={<BellOutlined />}
          aria-label={`通知${unreadCount > 0 ? `，${unreadCount} 条未读` : ''}`}
          style={{ background: 'var(--color-bg)', color: 'var(--color-dark)' }}
        />
      </Badge>
    </Dropdown>
  );
}
