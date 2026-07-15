import { Empty, Card, Row, Col } from 'antd';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend, BarChart, Bar } from 'recharts';
import { formatMoney, formatMoneyCompact, channelLabel, formatPercent } from '@/utils/format';
import { useChartColors } from '@/hooks/useChartColors';
import type { TrendPoint, MonthlyComparisonPoint, ChannelBreakdownItem, AfterSales } from '@/types';

interface FinanceChartsProps {
  trend: TrendPoint[];
  monthlyData: MonthlyComparisonPoint[];
  channelBreakdown: ChannelBreakdownItem[];
  afterSalesList: AfterSales[];
}

/** 财务报表中的所有图表组件（4 个图表集中管理）。
 *
 * 图表颜色通过 useChartColors() 在内部获取（深色模式适配）。
 * 数据由父组件传入，图表本身无状态。
 */
export default function FinanceCharts({ trend, monthlyData, channelBreakdown, afterSalesList }: FinanceChartsProps) {
  const chartColors = useChartColors();
  const emptyText = <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  // 销售渠道占比数据
  const channelData = channelBreakdown
    .filter((d) => d.income > 0)
    .map((d) => ({ name: channelLabel(d.channel), value: d.income, profit: d.profit, count: d.count }));

  // 售后解决方式分布
  const solutionData = [
    { name: '远程协助', value: afterSalesList.filter((a) => a.solution_type === 'remote').length },
    { name: '重新发货', value: afterSalesList.filter((a) => a.solution_type === 'reship').length },
    { name: '退款', value: afterSalesList.filter((a) => a.solution_type === 'refund').length },
    { name: '其他', value: afterSalesList.filter((a) => a.solution_type === 'other').length },
  ].filter((d) => d.value > 0);

  return (
    <>
      <Card title="销售渠道占比" style={{ marginTop: 16 }}>
        {channelData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={channelData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {channelData.map((_, idx) => (
                  <Cell key={idx} fill={chartColors.pieColors[idx % chartColors.pieColors.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip
                formatter={(v: number, name: string) => {
                  const item = channelData.find((d) => d.name === name);
                  return [`${formatMoney(v)}（利润 ${formatMoney(item?.profit || 0)} · ${item?.count || 0} 笔）`, name];
                }}
                contentStyle={{
                  background: chartColors.tooltipBg,
                  color: chartColors.tooltipText,
                  border: `1px solid ${chartColors.tooltipBorder}`,
                  borderRadius: 6,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-secondary)' }}>暂无数据</div>
        )}
      </Card>

      <Card title="近30天利润趋势" style={{ marginTop: 16 }}>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={trend}>
            <defs>
              <linearGradient id="colorProfit2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={chartColors.profit} stopOpacity={0.2} />
                <stop offset="95%" stopColor={chartColors.profit} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: chartColors.axisText }} axisLine={{ stroke: chartColors.axisLine }} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: chartColors.axisText }} tickFormatter={(v) => formatMoneyCompact(v)} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(v: number) => formatMoney(v)}
              contentStyle={{
                background: chartColors.tooltipBg,
                color: chartColors.tooltipText,
                border: `1px solid ${chartColors.tooltipBorder}`,
                borderRadius: 6,
              }}
            />
            <Area type="monotone" dataKey="profit" name="利润" stroke={chartColors.profit} strokeWidth={2} fill="url(#colorProfit2)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <Card
        title="月度收支对比"
        style={{ marginTop: 16 }}
        extra={<span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>最近 6 个月</span>}
      >
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={monthlyData} barGap={4} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 12, fill: chartColors.axisText }} axisLine={{ stroke: chartColors.axisLine }} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: chartColors.axisText }} tickFormatter={(v) => formatMoneyCompact(v)} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(v: number, name: string) => [formatMoney(v), name]}
              labelFormatter={(label) => `${label} · ${monthlyData.find((d) => d.month === label)?.tradeCount || 0} 笔交易`}
              contentStyle={{
                background: chartColors.tooltipBg,
                color: chartColors.tooltipText,
                border: `1px solid ${chartColors.tooltipBorder}`,
                borderRadius: 6,
              }}
            />
            <Legend />
            <Bar dataKey="income" name="收入" fill={chartColors.income} radius={[4, 4, 0, 0]} maxBarSize={48} />
            <Bar dataKey="cost" name="成本" fill={chartColors.cost} radius={[4, 4, 0, 0]} maxBarSize={48} />
            <Bar dataKey="profit" name="利润" fill={chartColors.profit} radius={[4, 4, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="售后解决方式分布">
            {solutionData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={solutionData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                    {solutionData.map((_, idx) => (
                      <Cell key={idx} fill={chartColors.pieColors[idx % chartColors.pieColors.length]} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip
                    contentStyle={{
                      background: chartColors.tooltipBg,
                      color: chartColors.tooltipText,
                      border: `1px solid ${chartColors.tooltipBorder}`,
                      borderRadius: 6,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-secondary)' }}>暂无数据</div>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
}
