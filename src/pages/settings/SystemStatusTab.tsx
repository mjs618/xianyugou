import { useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Result, Row, Skeleton, Space, Statistic, Tag } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { getMetrics, type MetricsResponse } from '@/services/metricsService';
import { formatDateTime } from '@/utils/date';
import { getErrorMessage } from '@/utils/error';

function summarizeError(error: string): string {
  const singleLine = error.replace(/\s+/g, ' ').trim();
  return singleLine.length > 160 ? `${singleLine.slice(0, 160)}…` : singleLine;
}

export default function SystemStatusTab() {
  const [metrics, setMetrics] = useState<MetricsResponse>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  const loadMetrics = async () => {
    setLoading(true);
    setError(undefined);
    try {
      setMetrics(await getMetrics());
    } catch (err) {
      setError(getErrorMessage(err, '运行指标加载失败'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMetrics();
  }, []);

  if (loading && !metrics) {
    return <Skeleton active paragraph={{ rows: 6 }} />;
  }

  if (error && !metrics) {
    return (
      <Result
        status="warning"
        title="运行状态加载失败"
        subTitle={error}
        extra={<Button type="primary" icon={<ReloadOutlined />} onClick={() => void loadMetrics()}>重新加载</Button>}
      />
    );
  }

  if (!metrics) return null;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {error && <Alert type="warning" showIcon message="刷新失败，当前展示上一次成功获取的数据" />}
      {metrics.sync.last_error && (
        <Alert
          type="error"
          showIcon
          message="最近一次同步存在错误"
          description={summarizeError(metrics.sync.last_error)}
        />
      )}
      {!metrics.backup.backup_dir_exists && (
        <Alert type="warning" showIcon message="服务器备份目录当前不可用" />
      )}

      <Row gutter={[12, 12]}>
        <Col xs={12} lg={6}>
          <Card size="small"><Statistic title="在线账号" value={metrics.accounts.online} suffix={`/ ${metrics.accounts.total}`} /></Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small"><Statistic title="24 小时同步成功" value={metrics.sync.last_24h_success} /></Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small"><Statistic title="服务器备份" value={metrics.backup.backup_count} suffix="份" /></Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card size="small"><Statistic title="未读通知" value={metrics.notifications_unread} /></Card>
        </Col>
      </Row>

      <Card
        type="inner"
        title="运行详情"
        extra={<Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={() => void loadMetrics()}>刷新</Button>}
      >
        <Descriptions column={{ xs: 1, md: 2 }} size="small">
          <Descriptions.Item label="同步调度器">
            <Tag color={metrics.scheduler_running ? 'success' : 'error'}>
              {metrics.scheduler_running ? '运行中' : '已停止'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="账号状态">
            在线 {metrics.accounts.online} / 暂停 {metrics.accounts.paused} / 失效 {metrics.accounts.invalid}
          </Descriptions.Item>
          <Descriptions.Item label="24 小时同步失败">{metrics.sync.last_24h_failed}</Descriptions.Item>
          <Descriptions.Item label="24 小时拉取订单">{metrics.sync.last_24h_fetched_orders}</Descriptions.Item>
          <Descriptions.Item label="24 小时新建交易">{metrics.sync.last_24h_created_transactions}</Descriptions.Item>
          <Descriptions.Item label="最近同步">{formatDateTime(metrics.sync.last_sync_at)}</Descriptions.Item>
          <Descriptions.Item label="最近备份">{formatDateTime(metrics.backup.last_backup_at)}</Descriptions.Item>
          <Descriptions.Item label="数据更新时间">{formatDateTime(metrics.timestamp)}</Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  );
}
