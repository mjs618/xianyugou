import { useEffect, useState } from 'react';
import { Card, Row, Col, DatePicker, Button, Space, Segmented, message, Spin, Form } from 'antd';
import { ExportOutlined, FileExcelOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getFinanceOverviewByRange, getTrend, getProductProfitStats, getCustomerValueStats, getMonthlyComparison, getChannelBreakdown } from '@/services/financeService';
import { createExpense, listExpenses } from '@/services/expenseService';
import { listTransactions, listByDateRange } from '@/services/transactionService';
import { getPendingTotal, getTotalPaid, listRebates } from '@/services/rebateService';
import { listAfterSales } from '@/services/afterSalesService';
import { exportTransactionsCSV, downloadFile, exportFinanceReportExcel, downloadBlob } from '@/utils/export';
import StatCard from '@/components/StatCard';
import { IncomeIcon, ProfitIcon, TradeIcon } from '@/components/RefinedIcons';
import type { FinanceOverview, TrendPoint, ProductProfitStat, CustomerValueStat, MonthlyComparisonPoint, RebateRecord, AfterSales, OperatingExpense, ChannelBreakdownItem, ChannelType } from '@/types';
import FinanceCharts from './finance/FinanceCharts';
import FinanceTables from './finance/FinanceTables';
import RebatePanel, { RebateStats } from './finance/RebatePanel';
import ExpenseModal from './finance/ExpenseModal';

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
  const [expenses, setExpenses] = useState<OperatingExpense[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [paidTotal, setPaidTotal] = useState(0);
  const [rangeType, setRangeType] = useState<RangeType>('month');
  const [customRange, setCustomRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [channelFilter, setChannelFilter] = useState<'all' | ChannelType>('all');
  const [channelBreakdown, setChannelBreakdown] = useState<ChannelBreakdownItem[]>([]);
  const [expenseModalOpen, setExpenseModalOpen] = useState(false);
  const [expenseSubmitting, setExpenseSubmitting] = useState(false);
  const [expenseForm] = Form.useForm();

  useEffect(() => {
    loadData();
  }, [rangeType, customRange, channelFilter]);

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
      const [rangeStart, rangeEnd] = range || [dayjs().startOf('month').toDate(), dayjs().endOf('month').toDate()];
      const channel = channelFilter === 'all' ? undefined : channelFilter;
      const [ov, tr, mc, ps, cs, rb, pt, pd, as, ex, cb] = await Promise.all([
        getFinanceOverviewByRange(rangeStart, rangeEnd, channel),
        getTrend(30, channel),
        getMonthlyComparison(6, channel),
        getProductProfitStats(rangeStart, rangeEnd, channel),
        getCustomerValueStats(10),
        listRebates(),
        getPendingTotal(),
        getTotalPaid(),
        listAfterSales(),
        listExpenses(rangeStart, rangeEnd),
        getChannelBreakdown(rangeStart, rangeEnd),
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
      setExpenses(ex);
      setChannelBreakdown(cb);
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

  const handleExportExcel = async () => {
    if (!overview) {
      message.warning('报表数据尚未加载完成');
      return;
    }
    const range = getDateRange();
    const [rangeStart, rangeEnd] = range || [dayjs().startOf('month').toDate(), dayjs().endOf('month').toDate()];
    try {
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

  const openExpenseModal = () => {
    expenseForm.setFieldsValue({
      category: '擦亮',
      amount: undefined,
      occurred_at: dayjs(),
      notes: '',
    });
    setExpenseModalOpen(true);
  };

  const handleCreateExpense = async () => {
    setExpenseSubmitting(true);
    try {
      const values = await expenseForm.validateFields();
      await createExpense({
        category: values.category,
        amount: values.amount,
        occurred_at: values.occurred_at.toDate(),
        notes: values.notes,
      });
      message.success('支出已记录');
      setExpenseModalOpen(false);
      loadData();
    } catch (err) {
      if (err instanceof Error) {
        message.error(err.message);
      }
    } finally {
      setExpenseSubmitting(false);
    }
  };

  const operatingExpenseTotal = overview?.operatingExpense ?? expenses.reduce((sum, item) => sum + item.amount, 0);

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
            <Segmented
              value={channelFilter}
              onChange={(v) => setChannelFilter(v as 'all' | ChannelType)}
              options={[
                { label: '全部渠道', value: 'all' },
                { label: '闲鱼', value: 'xianyu' },
                { label: '微信', value: 'wechat' },
                { label: '其他', value: 'other' },
              ]}
            />
            <Button icon={<PlusOutlined />} onClick={openExpenseModal}>记擦亮费</Button>
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
          <Col xs={12} sm={6}>
            <StatCard title="运营支出" value={operatingExpenseTotal} prefix="¥" icon={<TradeIcon />} color="var(--color-warning)" />
          </Col>
        </Row>
      </Card>

      <FinanceCharts
        trend={trend}
        monthlyData={monthlyData}
        channelBreakdown={channelBreakdown}
        afterSalesList={afterSalesList}
      />

      <FinanceTables
        products={products}
        customers={customers}
        expenses={expenses}
        onReload={loadData}
        onAddExpense={openExpenseModal}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 16, marginTop: 16 }}>
        <RebateStats rebates={rebates} pendingTotal={pendingTotal} paidTotal={paidTotal} />
      </div>

      <div style={{ marginTop: 16 }}>
        <RebatePanel
          rebates={rebates}
          pendingTotal={pendingTotal}
          paidTotal={paidTotal}
          onReload={loadData}
        />
      </div>

      <ExpenseModal
        open={expenseModalOpen}
        form={expenseForm}
        submitting={expenseSubmitting}
        onOk={handleCreateExpense}
        onCancel={() => setExpenseModalOpen(false)}
      />
    </div>
  );
}
