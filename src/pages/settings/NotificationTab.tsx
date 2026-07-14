import { useState } from 'react';
import { Card, Space, Descriptions, Tag, Alert, Button, message } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import {
  requestNotificationPermission,
  getNotificationPermission,
  runAllReminderChecks,
} from '@/services/notificationService';
import { useAppStore } from '@/store/useAppStore';

/** 通知设置 Tab：浏览器通知开关 + 提醒类型说明。状态自包含。 */
export default function NotificationTab() {
  const { refreshAll } = useAppStore();
  const [notifPermission, setNotifPermission] = useState(getNotificationPermission());

  const handleEnableNotification = async () => {
    try {
      const granted = await requestNotificationPermission();
      setNotifPermission(getNotificationPermission());
      if (granted) {
        message.success('通知已开启，将为您推送提醒');
        await runAllReminderChecks();
        refreshAll();
      } else {
        message.warning('通知权限未开启，请在浏览器设置中允许通知');
      }
    } catch (err) {
      console.error('开启通知失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleTestNotification = () => {
    if (notifPermission === 'granted') {
      try {
        new Notification('测试通知', { body: '闲鱼记账助手通知功能正常工作！' });
        message.success('测试通知已发送');
      } catch {
        message.error('通知发送失败');
      }
    } else {
      message.warning('请先开启通知权限');
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card type="inner" title={<span><BellOutlined /> 浏览器通知</span>}>
        <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
          <Descriptions.Item label="当前状态">
            {notifPermission === 'granted' ? (
              <Tag color="green">已开启</Tag>
            ) : notifPermission === 'denied' ? (
              <Tag color="red">已拒绝</Tag>
            ) : notifPermission === 'unsupported' ? (
              <Tag color="default">不支持</Tag>
            ) : (
              <Tag color="orange">未开启</Tag>
            )}
          </Descriptions.Item>
        </Descriptions>
        {notifPermission === 'denied' && (
          <Alert
            type="warning"
            message="通知权限已被拒绝"
            description={'请在浏览器地址栏点击锁图标，将通知权限改为"允许"，然后刷新页面。'}
            style={{ marginBottom: 16 }}
          />
        )}
        <Space>
          {notifPermission !== 'granted' && notifPermission !== 'denied' && notifPermission !== 'unsupported' && (
            <Button type="primary" icon={<BellOutlined />} onClick={handleEnableNotification}>
              开启通知
            </Button>
          )}
          {notifPermission === 'granted' && (
            <Button icon={<BellOutlined />} onClick={handleTestNotification}>
              发送测试通知
            </Button>
          )}
        </Space>
      </Card>
      <Card type="inner" title="提醒类型说明">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="质保到期提醒">
            质保到期前 3 天自动推送提醒（应用内通知 + 浏览器通知）
          </Descriptions.Item>
          <Descriptions.Item label="客户回访提醒">
            VIP/核心客户超过设定天数未交易时，自动推送回访提醒
          </Descriptions.Item>
          <Descriptions.Item label="返利结算提醒">
            有待结算返利时，每日推送提醒
          </Descriptions.Item>
        </Descriptions>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 12, marginTop: 12 }}>
          提醒检查在应用启动时和每 10 分钟自动执行一次。
        </p>
      </Card>
    </Space>
  );
}
