import { Card, Col, Row, Button } from 'antd';
import type { Customer } from '@/types';

interface ChurnRiskStats {
  blacklistCount: number;
  churnRiskCount: number;
}

interface CustomerStatsProps {
  customers: Map<number, Customer>;
  churnStats: ChurnRiskStats;
  onNavigate: (path: string) => void;
}

/** Dashboard 底部：客户等级分布 + 黑名单与流失预警。 */
export default function CustomerStats({ customers, churnStats, onNavigate }: CustomerStatsProps) {
  const list = Array.from(customers.values());
  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={8}>
        <Card title="客户等级分布" size="small">
          <Row gutter={16}>
            <Col span={6}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-dark)' }} className="tabular-nums">{customers.size}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>总客户</div>
              </div>
            </Col>
            <Col span={6}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-text-secondary)' }} className="tabular-nums">
                  {list.filter((c) => c.level === 'normal').length}
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>普通</div>
              </div>
            </Col>
            <Col span={6}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-warning)' }} className="tabular-nums">
                  {list.filter((c) => c.level === 'vip').length}
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>VIP</div>
              </div>
            </Col>
            <Col span={6}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-danger)' }} className="tabular-nums">
                  {list.filter((c) => c.level === 'core').length}
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>核心</div>
              </div>
            </Col>
          </Row>
        </Card>
      </Col>
      <Col xs={24} lg={16}>
        <Card title="黑名单与流失预警" size="small">
          <Row gutter={16}>
            <Col span={8}>
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-danger)' }} className="tabular-nums">
                  {churnStats.blacklistCount}
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>黑名单客户</div>
              </div>
            </Col>
            <Col span={8}>
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--theme-primary)' }} className="tabular-nums">
                  {churnStats.churnRiskCount}
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>高价值流失预警</div>
              </div>
            </Col>
            <Col span={8}>
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <Button type="link" onClick={() => onNavigate('/customers')} style={{ padding: 0 }}>管理客户 →</Button>
              </div>
            </Col>
          </Row>
        </Card>
      </Col>
    </Row>
  );
}
