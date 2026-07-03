import { useEffect, useState } from 'react';
import { Card, Row, Col, DatePicker, Button, Table, Space, Segmented, message, Tag, Popconfirm, Spin, Empty } from 'antd';
import { ExportOutlined, FileExcelOutlined } from '@ant-design/icons';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend, BarChart, Bar } from 'recharts';
import dayjs from 'dayjs';
import { getFinanceOverviewByRange, getTrend, getProductProfitStats, getCustomerValueStats, getMonthlyComparison } from '@/services/financeService';
import { listTransactions, listByDateRange } from '@/services/transactionService';
import { getPendingTotal, getTotalPaid, listRebates, markPaid, cancelRebate, batchPay } from '@/services/rebateService';
import { listAfterSales } from '@/services/afterSalesService';
import { exportTransactionsCSV, downloadFile, exportFinanceReportExcel, downloadBlob } from '@/utils/export';
import { formatMoney, formatPercent, formatMoneyCompact } from '@/utils/format';
import { formatDate } from '@/utils/date';
import StatCard from '@/components/StatCard';
import { IncomeIcon, ProfitIcon, TradeIcon, RebateIcon } from '@/components/RefinedIcons';
import { useChartColors } from '@/hooks/useChartColors';
import type { FinanceOverview, TrendPoint, ProductProfitStat, CustomerValueStat, MonthlyComparisonPoint, RebateRecord, AfterSales } from '@/types';

const { RangePicker } = DatePicker;

type RangeType = 'month' | 'prevMonth' | '3month' | '6month' | 'year' | 'custom';

export default function FinanceReport() {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [monthlyData, setMonthlyData] = useState<MonthlyComparisonPoint[]>([]);
  const [products, setProducts] = useState<ProductProfitStat[]>([]);
  const [customers, setCustomers] = useState<CustomerValueStat[]>([]);
  const [rebates, setRebates] = useState<RebateRecord[]>([]);
  const [afterSalesList, setAfterSalesList] = useState<AfterSales[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [paidTotal, setPaidTotal] = useState(0);
  const [rangeType, setRangeType] = useState<RangeType>('month');
  const [customRange, setCustomRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [selectedRebateKeys, setSelectedRebateKeys] = useState<number[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  // 深色模式下图表颜色适配（SVG 属性不支持 CSS var()，需通过 JS 动态绑定字符串值）
  const chartColors = useChartColors();

  useEffect(() => {
    loadData();
  }, [rangeType, customRange]);

  const getDateRange = (): [Date, Date] | undefined => {
    const now = dayjs();
    switch (rangeType) {
      case 'month':
        return [now.startOf('month').toDate(), now.endOf('month').toDate()];
      case 'prevMonth':
        return [now.subtract(1, 'month').startOf('month').toDate(), now.subtract(1, 'month').endOf('month').toDate()];
      case '3month':
        return [now.subtract(3, 'month').toDate(), now.toDate()];
      case '6month':
        return [now.subtract(6, 'month').toDate(), now.toDate()];
      case 'year':
        return [now.startOf('year').toDate(), now.toDate()];
      case 'custom':
        return customRange ? [customRange[0].toDate(), customRange[1].toDate()] : undefined;
      default:
        return undefined;
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const range = getDateRange();
      // 概览跟随所选时间范围；自定义未选择时回退到本月
      const [rangeStart, rangeEnd] = range || [dayjs().startOf('month').toDate(), dayjs().endOf('month').toDate()];
      const [ov, tr, mc, ps, cs, rb, pt, pd, as] = await Promise.all([
        getFinanceOverviewByRange(rangeStart, rangeEnd),
        getTrend(30),
        getMonthlyComparison(6),
        getProductProfitStats(rangeStart, rangeEnd),
        getCustomerValueStats(10),
        listRebates(),
        getPendingTotal(),
        getTotalPaid(),
        listAfterSales(),
      ]);
      setOverview(ov);
      setTrend(tr);
      setMonthlyData(mc);
      setProducts(ps.slice(0, 10));
      setCustomers(cs);
      setRebates(rb);
      setPendingTotal(pt);
      setPaidTotal(pd);
      setAfterSalesList(as);
    } catch (err) {
      console.error('加载财务报表失败:', err);
      message.error(err instanceof Error ? err.message : '加载财务报表失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const all = await listTransactions();
      const csv = exportTransactionsCSV(all);
      downloadFile(csv, `全部交易明细_${dayjs().format('YYYYMMDD')}.csv`, 'text/csv');
      message.success(`已导出 ${all.length} 条`);
    } catch (err) {
      console.error('导出交易明细失败:', err);
      message.error(err instanceof Error ? err.message : '导出失败，请重试');
    }
  };

  // 导出多 Sheet 财务报表 Excel（收支总览 + 交易明细 + 商品排行 + 客户排行 + 返利记录）
  const handleExportExcel = async () => {
    if (!overview) {
      message.warning('报表数据尚未加载完成');
      return;
    }
    const range = getDateRange();
    const [rangeStart, rangeEnd] = range || [dayjs().startOf('month').toDate(), dayjs().endOf('month').toDate()];
    try {
      // 按当前所选周期过滤交易明细
      const txs = await listByDateRange(rangeStart, rangeEnd);
      const blob = await exportFinanceReportExcel({
        overview,
        rangeStart,
        rangeEnd,
        transactions: txs,
        products,
        customers,
        rebates,
      });
      const rangeLabel = dayjs(rangeStart).format('YYYYMMDD');
      downloadBlob(blob, `财务报表_${rangeLabel}_${dayjs().format('YYYYMMDDHHmm')}.xlsx`);
      message.success(`已导出 Excel（含 ${txs.length} 条交易）`);
    } catch (err) {
      console.error('导出 Excel 失败:', err);
      message.error(err instanceof Error ? err.message : '导出 Excel 失败，请重试');
    }
  };

  const handleBatchPay = async () => {
    if (selectedRebateKeys.length === 0) return;
    setBatchLoading(true);
    try {
      const result = await batchPay(selectedRebateKeys);
      if (result.skipped > 0) {
        message.warning(`已结算 ${result.updated} 笔，跳过 ${result.skipped} 笔非法状态`);
      } else {
        message.success(`已批量结算 ${result.updated} 笔返利`);
      }
      setSelectedRebateKeys([]);
      loadData();
    } catch {
      message.error('批量结算失败');
    } finally {
      setBatchLoading(false);
    }
  };

  // 售后解决方式分布（基于售后工单的 solution_type）
  const solutionData = [
    { name: '远程协助', value: afterSalesList.filter((a) => a.solution_type === 'remote').length },
    { name: '重新发货', value: afterSalesList.filter((a) => a.solution_type === 'reship').length },
    { name: '退款', value: afterSalesList.filter((a) => a.solution_type === 'refund').length },
    { name: '其他', value: afterSalesList.filter((a) => a.solution_type === 'other').length },
  ].filter((d) => d.value > 0);
  const emptyText = <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <Card
        title="财务报表"
        extra={
          <Space>
            <Segmented
              value={rangeType}
              onChange={(v) => setRangeType(v as RangeType)}
              options={[
                { label: '本月', value: 'month' },
                { label: '上月', value: 'prevMonth' },
                { label: '近3月', value: '3month' },
                { label: '近6月', value: '6month' },
                { label: '本年', value: 'year' },
                { label: '自定义', value: 'custom' },
              ]}
            />
            {rangeType === 'custom' && (
              <RangePicker value={customRange} onChange={(v) => setCustomRange(v as any)} />
            )}
            <Button type="primary" icon={<FileExcelOutlined />} onClick={handleExportExcel}>导出 Excel</Button>
            <Button icon={<ExportOutlined />} onClick={handleExport}>导出明细</Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={12} sm={6}>
            <StatCard title="总收入" value={overview?.totalIncome || 0} change={overview?.incomeChange} icon={<IncomeIcon />} />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard title="总成本" value={overview?.totalCost || 0} prefix="¥" icon={<TradeIcon />} color="var(--color-info)" />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard title="净利润" value={overview?.totalProfit || 0} change={overview?.profitChange} icon={<ProfitIcon />} color="var(--color-success)" />
          </Col>
          <Col xs={12} sm={6}>
            <StatCard title="利润率" value={(overview?.profitRate || 0) * 100} precision={1} prefix="" suffix="%" icon={<ProfitIcon />} color="var(--color-purple)" />
          </Col>
        </Row>
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
          <Card title="商品利润排行">
            <Table
              rowKey="productName"
              dataSource={products}
              size="small"
              pagination={{ pageSize: 10 }}
              locale={{ emptyText }}
              columns={[
                { title: '商品', dataIndex: 'productName', ellipsis: true },
                { title: '笔数', dataIndex: 'count', width: 60, align: 'center' as const },
                { title: '收入', dataIndex: 'totalIncome', width: 100, render: (v: number) => formatMoney(v), align: 'right' as const },
                { title: '利润', dataIndex: 'totalProfit', width: 100, render: (v: number) => <span style={{ color: 'var(--color-success)' }}>{formatMoney(v)}</span>, align: 'right' as const },
                { title: '利润率', dataIndex: 'profitRate', width: 80, render: (v: number) => formatPercent(v), align: 'right' as const },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="客户消费排行">
            <Table
              rowKey="customerId"
              dataSource={customers}
              size="small"
              pagination={{ pageSize: 10 }}
              locale={{ emptyText }}
              columns={[
                { title: '客户', dataIndex: 'nickname', ellipsis: true },
                { title: '笔数', dataIndex: 'tradeCount', width: 60, align: 'center' as const },
                { title: '累计消费', dataIndex: 'totalSpent', width: 120, render: (v: number) => formatMoney(v), align: 'right' as const },
                {
                  title: '等级',
                  dataIndex: 'level',
                  width: 70,
                  render: (l: string) => l === 'core' ? '核心' : l === 'vip' ? 'VIP' : '普通',
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="返利支出统计">
            <Row gutter={16}>
              <Col span={8}>
                <StatCard title="累计返利" value={paidTotal} prefix="¥" icon={<RebateIcon />} color="var(--color-success)" />
              </Col>
              <Col span={8}>
                <StatCard title="待结算" value={pendingTotal} prefix="¥" icon={<RebateIcon />} color="var(--theme-primary)" />
              </Col>
              <Col span={8}>
                <StatCard title="返利笔数" value={rebates.length} precision={0} prefix="" icon={<RebateIcon />} color="var(--color-info)" />
              </Col>
            </Row>
          </Card>
        </Col>
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

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title="返利结算"
            extra={
              <Space>
                {selectedRebateKeys.length > 0 && (
                  <Popconfirm title={`确认批量结算选中的 ${selectedRebateKeys.length} 笔返利？`} onConfirm={handleBatchPay}>
                    <Button type="primary" loading={batchLoading}>批量结算（{selectedRebateKeys.length}）</Button>
                  </Popconfirm>
                )}
                <span style={{ color: 'var(--color-text-secondary)' }}>待结算 {pendingTotal} 元</span>
              </Space>
            }
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={rebates}
              size="small"
              pagination={{ pageSize: 10 }}
              locale={{ emptyText }}
              rowSelection={{
                selectedRowKeys: selectedRebateKeys,
                onChange: (keys) => setSelectedRebateKeys(keys as number[]),
                getCheckboxProps: (r: RebateRecord) => ({ disabled: r.status !== 'pending' }),
              }}
              columns={[
                { title: '介绍人ID', dataIndex: 'referrer_id', width: 90 },
                { title: '买家ID', dataIndex: 'buyer_id', width: 90 },
                { title: '返利金额', dataIndex: 'amount', width: 100, render: (v: number) => <span style={{ color: 'var(--theme-primary)', fontWeight: 600 }}>{formatMoney(v)}</span>, align: 'right' as const },
                { title: '比例', dataIndex: 'rate', width: 70, render: (v: number) => `${Math.round(v * 100)}%`, align: 'center' as const },
                { title: '状态', dataIndex: 'status', width: 90, render: (s: string) => {
                  const map: Record<string, { label: string; color: string }> = { pending: { label: '待结算', color: 'orange' }, paid: { label: '已支付', color: 'green' }, cancelled: { label: '已取消', color: 'default' } };
                  return <Tag color={map[s].color}>{map[s].label}</Tag>;
                }},
                { title: '创建时间', dataIndex: 'created_at', width: 140, render: (v: Date) => formatDate(v) },
                { title: '支付时间', dataIndex: 'paid_at', width: 140, render: (v?: Date) => v ? formatDate(v) : '-' },
                { title: '操作', width: 140, render: (_: unknown, r: RebateRecord) => (
                  <Space size={4}>
                    {r.status === 'pending' && (
                      <>
                        <Popconfirm title="确认标记为已支付？" onConfirm={async () => { await markPaid(r.id!); message.success('已标记为已支付'); loadData(); }}>
                          <Button size="small" type="primary">结算</Button>
                        </Popconfirm>
                        <Popconfirm title="确认取消该返利？" onConfirm={async () => { await cancelRebate(r.id!); message.success('已取消'); loadData(); }}>
                          <Button size="small" danger>取消</Button>
                        </Popconfirm>
                      </>
                    )}
                  </Space>
                )},
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
