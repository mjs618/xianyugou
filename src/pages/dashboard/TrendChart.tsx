import { Card, Col, Empty, List, Row, Button } from 'antd';
import { TrophyOutlined } from '@ant-design/icons';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { formatMoney } from '@/utils/format';
import { useChartColors } from '@/hooks/useChartColors';
import type { TrendPoint, ReferrerRanking } from '@/types';

interface TrendChartProps {
  trend: TrendPoint[];
  trendDays: number;
  onTrendDaysChange: (days: number) => void;
  rankings: ReferrerRanking[];
  onNavigate: (path: string) => void;
}

/** Dashboard 中部：交易趋势 AreaChart + 最佳介绍人 List 两栏布局。 */
export default function TrendChart({ trend, trendDays, onTrendDaysChange, rankings, onNavigate }: TrendChartProps) {
  const chartColors = useChartColors();

  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={16}>
        <Card
          title="交易趋势"
          extra={
            <div style={{ display: 'flex', gap: 4 }}>
              {[7, 30, 90].map((d) => (
                <Button key={d} size="small" type={trendDays === d ? 'primary' : 'default'} onClick={() => onTrendDaysChange(d)}>
                  {d}天
                </Button>
              ))}
            </div>
          }
        >
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trend}>
              <defs>
                <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.income} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={chartColors.income} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.profit} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={chartColors.profit} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: chartColors.axisText }} axisLine={{ stroke: chartColors.axisLine }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: chartColors.axisText }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v: number) => formatMoney(v)}
                contentStyle={{
                  background: chartColors.tooltipBg,
                  color: chartColors.tooltipText,
                  border: `1px solid ${chartColors.tooltipBorder}`,
                  borderRadius: 6,
                }}
              />
              <Area type="monotone" dataKey="income" name="收入" stroke={chartColors.income} strokeWidth={2} fill="url(#colorIncome)" />
              <Area type="monotone" dataKey="profit" name="利润" stroke={chartColors.profit} strokeWidth={2} fill="url(#colorProfit)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Card title={<span><TrophyOutlined style={{ color: 'var(--color-warning)', marginRight: 8 }} />最佳介绍人</span>} extra={<Button type="link" size="small" onClick={() => onNavigate('/referral')}>查看全部</Button>}>
          {rankings.length === 0 ? (
            <Empty description="暂无介绍数据" />
          ) : (
            <List
              dataSource={rankings}
              renderItem={(r, idx) => (
                <List.Item onClick={() => onNavigate(`/customers/${r.referrerId}`)} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: 22,
                          height: 22,
                          borderRadius: '50%',
                          background: idx < 3 ? 'var(--theme-primary)' : 'var(--color-border)',
                          color: idx < 3 ? '#fff' : 'var(--color-text-secondary)',
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        {idx + 1}
                      </span>
                      <span style={{ fontWeight: 500 }}>{r.nickname}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>介绍 {r.introducedCount} 人</div>
                      <div style={{ color: 'var(--theme-primary)', fontWeight: 600 }} className="tabular-nums">{formatMoney(r.broughtRevenue)}</div>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          )}
        </Card>
      </Col>
    </Row>
  );
}
