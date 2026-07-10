import { useEffect, useState, useMemo } from 'react';
import { Card, Row, Col, List, Tag, Empty, Skeleton, Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  WarningOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import StatCard from '@/components/StatCard';
import { IncomeIcon, ProfitIcon, TradeIcon, NewCustomerIcon, WarrantyIcon, ToolIcon, RebateIcon } from '@/components/RefinedIcons';
import WarrantyTag from '@/components/WarrantyTag';
import { getFinanceOverview, getTrend, getNewCustomerCount, getNewCustomerCountByRange, getProductProfitStats } from '@/services/financeService';
import { getReferrerRankings } from '@/services/referralService';
import { getUrgentTransactions } from '@/services/warrantyService';
import { listTransactions } from '@/services/transactionService';
import { listCustomers, getChurnRiskStats } from '@/services/customerService';
import { formatMoney, formatPercent } from '@/utils/format';
import { formatDate } from '@/utils/date';
import { getMonthRange, getPrevMonthRange } from '@/utils/date';
import { useAppStore } from '@/store/useAppStore';
import { useChartColors } from '@/hooks/useChartColors';
import type { FinanceOverview, TrendPoint, ReferrerRanking, Transaction, Customer, ProductProfitStat } from '@/types';

/** 仪表盘告警统计卡（质保到期/待处理售后/待结算返利 共用样式） */
function AlertStatCard({ icon, label, value, variant, onClick }: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  variant: 'danger' | 'warning' | 'success';
  onClick: () => void;
}) {
  const palette = {
    danger: { light: 'var(--color-danger-light)', border: 'var(--color-danger-border)', color: 'var(--color-danger)' },
    warning: { light: 'var(--color-warning-light)', border: 'var(--color-warning-border)', color: 'var(--theme-primary)' },
    success: { light: 'var(--color-success-light)', border: 'var(--color-success-border)', color: 'var(--color-success)' },
  }[variant];
  return (
    <Card hoverable onClick={onClick}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: `linear-gradient(135deg, ${palette.light} 0%, ${palette.border} 100%)`,
          color: palette.color,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: `1px solid ${palette.border}`,
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.5)',
        }}>
          {icon}
        </div>
        <div>
          <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>{label}</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: palette.color, lineHeight: 1.2 }} className="tabular-nums">{value}</div>
        </div>
      </div>
    </Card>
  );
}

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
  const [trendDays, setTrendDays] = useState(30);

  const churnStats = useMemo(
    () => getChurnRiskStats(Array.from(customers.values()), allTrades),
    [customers, allTrades]
  );

  // 深色模式下图表颜色适配（SVG 属性不支持 CSS var()，需通过 JS 动态绑定字符串值）
  const chartColors = useChartColors();

  useEffect(() => {
    loadData();
  }, [trendDays]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const prev = getPrevMonthRange(new Date());
      const monthRange = getMonthRange(new Date());
      const [ov, tr, nc, prevNc, rk, urgent, trades, custs, ps] = await Promise.all([
        getFinanceOverview(),
        getTrend(trendDays),
        getNewCustomerCount(),
        getNewCustomerCountByRange(prev.start, prev.end),
        getReferrerRankings(),
        getUrgentTransactions(),
        listTransactions(),
        listCustomers(),
        getProductProfitStats(monthRange.start, monthRange.end),
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
          <StatCard title="本月总收入" value={overview.totalIncome} change={overview.incomeChange} icon={<IncomeIcon />} onClick={() => navigate('/finance')} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="本月净利润" value={overview.totalProfit} change={overview.profitChange} icon={<ProfitIcon />} color="var(--color-success)" onClick={() => navigate('/finance')} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="交易笔数" value={overview.tradeCount} precision={0} prefix="" change={overview.tradeCountChange} icon={<TradeIcon />} color="var(--color-info)" onClick={() => navigate('/transactions')} />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard title="本月新客户" value={newCustomers} precision={0} prefix="" change={prevNewCustomers > 0 ? (newCustomers - prevNewCustomers) / prevNewCustomers : 0} icon={<NewCustomerIcon />} color="var(--color-purple)" onClick={() => navigate('/customers')} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<WarrantyIcon />} label="质保即将到期" value={pendingSummary.warrantyUrgent} variant="danger" onClick={() => navigate('/warranty')} />
        </Col>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<ToolIcon />} label="待处理售后" value={pendingSummary.afterSalesPending} variant="warning" onClick={() => navigate('/after-sales')} />
        </Col>
        <Col xs={24} lg={8}>
          <AlertStatCard icon={<RebateIcon />} label="待结算返利" value={pendingSummary.rebatePending} variant="success" onClick={() => navigate('/finance')} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title="交易趋势"
            extra={
              <div style={{ display: 'flex', gap: 4 }}>
                {[7, 30, 90].map((d) => (
                  <Button key={d} size="small" type={trendDays === d ? 'primary' : 'default'} onClick={() => setTrendDays(d)}>
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
          <Card title={<span><TrophyOutlined style={{ color: 'var(--color-warning)', marginRight: 8 }} />最佳介绍人</span>} extra={<Button type="link" size="small" onClick={() => navigate('/referral')}>查看全部</Button>}>
            {rankings.length === 0 ? (
              <Empty description="暂无介绍数据" />
            ) : (
              <List
                dataSource={rankings}
                renderItem={(r, idx) => (
                  <List.Item onClick={() => navigate(`/customers/${r.referrerId}`)} style={{ cursor: 'pointer' }}>
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

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="最近交易" size="small">
            <List
              size="small"
              dataSource={recentTrades}
              locale={{ emptyText: '暂无交易' }}
              renderItem={(t) => {
                const c = customers.get(t.customer_id);
                return (
                  <List.Item
                    style={{ cursor: 'pointer', padding: '8px 0' }}
                    onClick={() => navigate(`/transactions/${t.id}`)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {t.product_name}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                          {c?.xianyu_nickname || '-'} · {formatDate(t.trade_at)}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', marginLeft: 12 }}>
                        <div style={{ color: 'var(--color-dark)', fontWeight: 600 }} className="tabular-nums">
                          {formatMoney(t.sale_price)}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--color-success)' }} className="tabular-nums">
                          利润 {formatMoney(t.profit)}
                        </div>
                      </div>
                    </div>
                  </List.Item>
                );
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title="本月商品销售排行"
            size="small"
            extra={<Button type="link" size="small" onClick={() => navigate('/finance')}>查看全部</Button>}
          >
            {productStats.length === 0 ? (
              <Empty description="本月暂无销售数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                size="small"
                dataSource={productStats}
                renderItem={(p, idx) => (
                  <List.Item style={{ padding: '8px 0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
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
                            flexShrink: 0,
                          }}
                        >
                          {idx + 1}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {p.productName}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                            {p.count} 笔 · 利润率 {formatPercent(p.profitRate)}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', marginLeft: 12 }}>
                        <div style={{ color: 'var(--color-success)', fontWeight: 600 }} className="tabular-nums">
                          {formatMoney(p.totalProfit)}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }} className="tabular-nums">
                          收入 {formatMoney(p.totalIncome)}
                        </div>
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {urgentTrades.length > 0 && (
        <Card title={<span><WarningOutlined style={{ color: 'var(--color-danger)', marginRight: 8 }} />质保即将到期交易</span>} style={{ marginTop: 16 }}>
          <List
            dataSource={urgentTrades.slice(0, 5)}
            renderItem={(t) => (
              <List.Item
                actions={[<Button type="link" size="small" onClick={() => navigate(`/transactions/${t.id}`)}>详情</Button>]}
              >
                <List.Item.Meta
                  title={t.product_name}
                  description={
                    <span style={{ fontSize: 12 }}>
                      到期: {formatDate(t.warranty_end, 'YYYY-MM-DD HH:mm')} <WarrantyTag warrantyEnd={t.warranty_end} status={t.status} />
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

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
                    {Array.from(customers.values()).filter((c) => c.level === 'normal').length}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>普通</div>
                </div>
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-warning)' }} className="tabular-nums">
                    {Array.from(customers.values()).filter((c) => c.level === 'vip').length}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>VIP</div>
                </div>
              </Col>
              <Col span={6}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-danger)' }} className="tabular-nums">
                    {Array.from(customers.values()).filter((c) => c.level === 'core').length}
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
                  <Button type="link" onClick={() => navigate('/customers')} style={{ padding: 0 }}>管理客户 →</Button>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
