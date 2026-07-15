import { Card, Col, Row, Statistic } from 'antd';
import { formatPercent } from '@/utils/format';

interface StatsCardsProps {
  totalCount: number;
  pendingCount: number;
  overdueCount: number;
  rate: number;
  avgDurationHours: number;
}

/** 顶部售后统计卡：总数/待处理/超时未完成/售后率/平均处理时长。 */
export default function StatsCards({ totalCount, pendingCount, overdueCount, rate, avgDurationHours }: StatsCardsProps) {
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={12} sm={6}>
        <Card><Statistic title="售后总数" value={totalCount} /></Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card><Statistic title="待处理" value={pendingCount} valueStyle={{ color: 'var(--color-danger)' }} /></Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card><Statistic title="超时未完成" value={overdueCount} valueStyle={{ color: 'var(--color-danger)' }} /></Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card><Statistic title="售后率" value={formatPercent(rate)} /></Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card><Statistic title="平均处理时长" value={avgDurationHours} suffix="小时" /></Card>
      </Col>
    </Row>
  );
}
