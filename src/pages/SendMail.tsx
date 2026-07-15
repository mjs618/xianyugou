import { useEffect, useState, useCallback } from 'react';
import { Card, Tabs, Tag, Button, Space, Alert, Typography } from 'antd';
import {
  SendOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MailOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { checkMailServer } from '@/services/mailService';
import { BACKEND_POLL_INTERVAL_MS } from '@/config/constants';
import SingleSend from './sendmail/SingleSend';
import BatchSend from './sendmail/BatchSend';
import MailHistory from './sendmail/MailHistory';

const { Text } = Typography;

/** 发货邮件主页面：检测邮件服务 + 三 Tab（单条/批量/历史）编排。 */
export default function SendMail() {
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [activeTab, setActiveTab] = useState('single');

  const checkServer = useCallback(async () => {
    const ok = await checkMailServer();
    setServerOnline(ok);
    return ok;
  }, []);

  useEffect(() => {
    checkServer();
    const timer = setInterval(checkServer, BACKEND_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [checkServer]);

  return (
    <Card
      title={<span><MailOutlined /> 发货邮件</span>}
      extra={
        <Space>
          {serverOnline === null ? (
            <Tag color="default">检测中...</Tag>
          ) : serverOnline ? (
            <Tag icon={<CheckCircleOutlined />} color="success">邮件服务已连接</Tag>
          ) : (
            <Tag icon={<CloseCircleOutlined />} color="error">邮件服务未运行</Tag>
          )}
          <Button size="small" icon={<ReloadOutlined />} onClick={checkServer}>刷新</Button>
        </Space>
      }
    >
      {serverOnline === false && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="本地邮件服务未运行"
          description={
            <span>
              请在项目根目录新开一个终端，执行命令启动邮件服务：
              <Text code copyable style={{ marginLeft: 8 }}>npm run mail-server</Text>
            </span>
          }
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'single',
            label: <span><SendOutlined /> 单条发送</span>,
            children: <SingleSend checkServer={checkServer} />,
          },
          {
            key: 'batch',
            label: <span><ThunderboltOutlined /> 批量发送</span>,
            children: <BatchSend checkServer={checkServer} />,
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> 发送历史</span>,
            children: <MailHistory />,
          },
        ]}
      />
    </Card>
  );
}
