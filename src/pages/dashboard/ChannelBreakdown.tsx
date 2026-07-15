import { Card, Col, Empty, Row, Tag } from 'antd';
import { formatMoney, channelLabel, channelColorMap } from '@/utils/format';
import type { ChannelBreakdownItem } from '@/types';

interface ChannelBreakdownProps {
  breakdown: ChannelBreakdownItem[];
}

/** Dashboard：本月渠道收入对比（条形图 + 标签 + 数据展示）。 */
export default function ChannelBreakdown({ breakdown }: ChannelBreakdownProps) {
  if (breakdown.length === 0) {
    return (
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={24}>
          <Card title="本月渠道收入对比" size="small">
            <Empty description="本月暂无交易数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </Card>
        </Col>
      </Row>
    );
  }
  const maxIncome = Math.max(...breakdown.map((b) => b.income), 1);
  // 渠道条颜色：根据 channelColorMap 映射到 CSS 变量，未匹配走中性色
  const channelBarColorMap: Record<string, string> = {
    blue: 'var(--theme-primary)',
    green: 'var(--color-success)',
  };
  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={24}>
        <Card title="本月渠道收入对比" size="small">
          <Row gutter={24}>
            {breakdown.map((ch) => {
              const pct = Math.max((ch.income / maxIncome) * 100, 2);
              const barColor = channelBarColorMap[channelColorMap[ch.channel]] ?? 'var(--color-text-tertiary)';
              return (
                <Col xs={24} sm={8} key={ch.channel}>
                  <div style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Tag color={channelColorMap[ch.channel] || 'default'}>{channelLabel(ch.channel)}</Tag>
                    <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }} className="tabular-nums">{ch.count} 笔</span>
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 600 }} className="tabular-nums">
                    {formatMoney(ch.income)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-success)', marginBottom: 8 }} className="tabular-nums">
                    利润 {formatMoney(ch.profit)}
                  </div>
                  <div style={{ background: 'var(--color-bg)', height: 6, borderRadius: 3 }}>
                    <div style={{
                      width: `${pct}%`,
                      height: '100%',
                      borderRadius: 3,
                      background: barColor,
                      transition: 'width 0.3s ease',
                    }} />
                  </div>
                </Col>
              );
            })}
          </Row>
        </Card>
      </Col>
    </Row>
  );
}
