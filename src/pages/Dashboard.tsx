import { useEffect, useState, useMemo } from 'react';
import { Card, Row, Col, Skeleton, Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';
import StatCard from '@/components/StatCard';
import { IncomeIcon, ProfitIcon, TradeIcon, NewCustomerIcon, WarrantyIcon, ToolIcon, RebateIcon } from '@/components/RefinedIcons';
import { getFinanceOverview, getTrend, getNewCustomerCount, getNewCustomerCountByRange, getProductProfitStats, getChannelBreakdown } from '@/services/financeService';
import { getReferrerRankings } from '@/services/referralService';
import { getUrgentTransactions } from '@/services/warrantyService';
import { listTransactions } from '@/services/transactionService';
import { listCustomers, getChurnRiskStats } from '@/services/customerService';
import { getMonthRange, getPrevMonthRange } from '@/utils/date';
import { useAppStore } from '@/store/useAppStore';
import type { FinanceOverview, TrendPoint, ReferrerRanking, Transaction, Customer, ProductProfitStat, ChannelBreakdownItem } from '@/types';
import AlertStatCard from './dashboard/AlertStatCard';
import TrendChart from './dashboard/TrendChart';
import DashboardLists from './dashboard/DashboardLists';
import ChannelBreakdown from './dashboard/ChannelBreakdown';
import UrgentWarrantyTrades from './dashboard/UrgentWarrantyTrades';
import CustomerStats from './dashboard/CustomerStats';

export default function Dashboard() {
  const navigate = useNavigate();
  const { pendingSummary } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [newCustomers, setNewCustomers] = useState(0);
  const [prevNewCustomers, setPrevNewCustomers] = useState(0);
  const [rankings, setRankings] = useState<ReferrerRanking[]>([]);
  const [urgentTrades, setUrgentTrades] = useState<Transaction[]>([]);
  const [recentTrades, setRecentTrades] = useState<Transaction[]>([]);
  const [customers, setCustomers] = useState<Map<number, Customer>>(new Map());
  const [allTrades, setAllTrades] = useState<Transaction[]>([]);
  const [productStats, setProductStats] = useState<ProductProfitStat[]>([]);
  const [channelBreakdown, setChannelBreakdown] = useState<ChannelBreakdownItem[]>([]);
  const [trendDays, setTrendDays] = useState(30);

  const churnStats = useMemo(
    () => getChurnRiskStats(Array.from(customers.values()), allTrades),
    [customers, allTrades]
  );

  useEffect(() => {
    loadData();
  }, [trendDays]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const prev = getPrevMonthRange(new Date());
      const monthRange = getMonthRange(new Date());
      const [ov, tr, nc, prevNc, rk, urgent, trades, custs, ps, cb] = await Promise.all([
        getFinanceOverview(),
        getTrend(trendDays),
        getNewCustomerCount(),
        getNewCustomerCountByRange(prev.start, prev.end),
        getReferrerRankings(),
        getUrgentTransactions(),
        listTransactions(),
        listCustomers(),
        getProductProfitStats(monthRange.start, monthRange.end),
        getChannelBreakdown(monthRange.start, monthRange.end),
      ]);
      setOverview(ov);
      setTrend(tr);
      setNewCustomers(nc);
      setPrevNewCustomers(prevNc);
      setRankings(rk.slice(0, 3));
      setUrgentTrades(urgent);
      setRecentTrades(trades.filter((t) => !t.deleted_at).slice(0, 10));
      setCustomers(new Map(custs.map((c) => [c.id!, c])));
      setAllTrades(trades);
      setProductStats(ps.slice(0, 5));
      setChannelBreakdown(cb);
    } catch (err) {
      console.error('Dashboard 数据加载失败:', err);
      setError(err instanceof Error ? err.message : '数据加载失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div>
        <Row gutter={[16, 16]}>
          {[1, 2, 3, 4].map((i) => (
            <Col key={i} xs={24} sm={12} lg={6}>
              <Card><Skeleton active paragraph={{ rows: 2 }} /></Card>
            </Col>
          ))}
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} lg={16}>
            <Card title={<Skeleton.Input active size="small" />}>
              <Skeleton active paragraph={{ rows: 6 }} />
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Card title={<Skeleton.Input active size="small" />}>
              <Skeleton active paragraph={{ rows: 5 }} />
            </Card>
          </Col>
        </Row>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <Result
        status="error"
        title="数据加载失败"
        subTitle={error || '未知错误'}
        extra={<Button type="primary" onClick={() => loadData()}>重新加载</Button>}
      />
    );
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="本月总收入" value={overview.totalIncome} change={overview.incomeChange} icon={<IncomeIcon />} to="/finance" />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="本月净利润" value={overview.totalProfit} change={overview.profitChange} icon={<ProfitIcon />} color="var(--color-success)" to="/finance" />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="交易笔数" value={overview.tradeCount} precision={0} prefix="" change={overview.tradeCountChange} icon={<TradeIcon />} color="var(--color-info)" to="/transactions" />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="本月新客户" value={newCustomers} precision={0} prefix="" change={prevNewCustomers > 0 ? (newCustomers - prevNewCustomers) / prevNewCustomers : 0} icon={<NewCustomerIcon />} color="var(--color-purple)" to="/customers" />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<WarrantyIcon />} label="质保即将到期" value={pendingSummary.warrantyUrgent} variant="danger" to="/warranty" />
        </Col>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<ToolIcon />} label="待处理售后" value={pendingSummary.afterSalesPending} variant="warning" to="/after-sales" />
        </Col>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<RebateIcon />} label="待结算返利" value={pendingSummary.rebatePending} variant="success" to="/finance" />
        </Col>
      </Row>

      <TrendChart
        trend={trend}
        trendDays={trendDays}
        onTrendDaysChange={setTrendDays}
        rankings={rankings}
        onNavigate={navigate}
      />

      <DashboardLists
        recentTrades={recentTrades}
        customers={customers}
        productStats={productStats}
        onNavigate={navigate}
      />

      <ChannelBreakdown breakdown={channelBreakdown} />

      <UrgentWarrantyTrades trades={urgentTrades} onNavigate={navigate} />

      <CustomerStats
        customers={customers}
        churnStats={churnStats}
        onNavigate={navigate}
      />
    </div>
  );
}
