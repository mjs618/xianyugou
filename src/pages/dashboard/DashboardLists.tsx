import { Card, Col, Empty, List, Row, Button } from 'antd';
import { formatMoney, formatPercent } from '@/utils/format';
import { formatDate } from '@/utils/date';
import type { Transaction, Customer, ProductProfitStat } from '@/types';

interface DashboardListsProps {
  recentTrades: Transaction[];
  customers: Map<number, Customer>;
  productStats: ProductProfitStat[];
  onNavigate: (path: string) => void;
}

/** Dashboard 列表区：最近交易 + 本月商品销售排行两栏。 */
export default function DashboardLists({ recentTrades, customers, productStats, onNavigate }: DashboardListsProps) {
  return (
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
                  onClick={() => onNavigate(`/transactions/${t.id}`)}
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
          extra={<Button type="link" size="small" onClick={() => onNavigate('/finance')}>查看全部</Button>}
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
  );
}
