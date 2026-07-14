import { useEffect, useState, useMemo } from 'react';
import { Card, Table, Button, Space, Empty, Spin, Tag, Row, Col, Select, InputNumber, Statistic, message } from 'antd';
import ReactFlow, { Background, Controls, type Node, type Edge, Handle, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import { TrophyOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getReferrerRankings, getReferralTree } from '@/services/referralService';
import { listCustomers } from '@/services/customerService';
import { formatMoney } from '@/utils/format';
import type { ReferrerRanking, ReferralTreeNode, Customer } from '@/types';

const medals = ['1', '2', '3'];

// 自定义节点
function ReferralNode({ data }: { data: { name: string; revenue: number; level: number; isVip: boolean } }) {
  return (
    <div className={`referral-node ${data.isVip ? 'vip' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="node-name">{data.name}</div>
      <div className="node-revenue">{formatMoney(data.revenue)}</div>
      {data.level > 0 && <div style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>L{data.level}</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { referral: ReferralNode };

export default function ReferralGraph() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlCustomerId = searchParams.get('customerId');
  const [loading, setLoading] = useState(true);
  const [rankings, setRankings] = useState<ReferrerRanking[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [rootId, setRootId] = useState<number | undefined>(urlCustomerId ? Number(urlCustomerId) : undefined);
  const [tree, setTree] = useState<ReferralTreeNode | null>(null);
  const [sortBy, setSortBy] = useState<'revenue' | 'count'>('revenue');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ranks, list] = await Promise.all([getReferrerRankings(), listCustomers()]);
      setRankings(ranks);
      setCustomers(list.filter((c) => !c.deleted_at));
      // 优先使用 URL 参数指定的客户，否则选介绍人数最多的
      if (!rootId) {
        if (urlCustomerId) {
          setRootId(Number(urlCustomerId));
        } else if (ranks.length > 0) {
          setRootId(ranks[0].referrerId);
        }
      }
    } catch (err) {
      console.error('加载推荐数据失败:', err);
      message.error(err instanceof Error ? err.message : '加载推荐数据失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (rootId) {
      getReferralTree(rootId)
        .then(setTree)
        .catch((err: unknown) => {
          console.error('加载推荐树失败:', err);
          message.error(err instanceof Error ? err.message : '加载推荐树失败，请重试');
        });
    } else {
      setTree(null);
    }
  }, [rootId]);

  // 构建 React Flow 节点和边
  const { nodes, edges } = useMemo(() => {
    if (!tree) return { nodes: [] as Node[], edges: [] as Edge[] };
    const ns: Node[] = [];
    const es: Edge[] = [];

    const layout = (node: ReferralTreeNode, x: number, y: number): number => {
      const vipLevels = ['vip', 'core'];
      const customer = customers.find((c) => c.id === node.id);
      ns.push({
        id: String(node.id),
        type: 'referral',
        position: { x, y },
        data: { name: node.name, revenue: node.totalRevenue, level: node.level, isVip: !!customer && vipLevels.includes(customer.level) },
      });
      if (node.children.length === 0) return x + 140;

      let childX = x;
      const childY = y + 100;
      for (const child of node.children) {
        const startX = childX;
        const endX = layout(child, childX, childY);
        es.push({
          id: `${node.id}-${child.id}`,
          source: String(node.id),
          target: String(child.id),
          animated: true,
          label: formatMoney(child.totalRevenue),
          style: { stroke: 'var(--theme-primary)', strokeWidth: 2 },
        });
        childX = endX + 60;
      }
      return childX - 60;
    };

    layout(tree, 0, 0);
    return { nodes: ns, edges: es };
  }, [tree, customers]);

  const sortedRankings = [...rankings].sort((a, b) =>
    sortBy === 'revenue' ? b.broughtRevenue - a.broughtRevenue : b.introducedCount - a.introducedCount
  );

  // 汇总统计
  const totalReferrers = rankings.length;
  const totalIntroduced = rankings.reduce((s, r) => s + r.introducedCount, 0);
  const totalBroughtRevenue = rankings.reduce((s, r) => s + r.broughtRevenue, 0);
  const totalPaidRebate = rankings.reduce((s, r) => s + r.paidRebate, 0);
  const totalPendingRebate = rankings.reduce((s, r) => s + r.pendingRebate, 0);

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="介绍人总数" value={totalReferrers} suffix="人" /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="累计介绍成交" value={totalIntroduced} suffix="笔" /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="带来成交额" value={totalBroughtRevenue} precision={2} prefix="¥" /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="已付返利" value={totalPaidRebate} precision={2} prefix="¥" valueStyle={{ color: 'var(--color-success)' }} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="待付返利" value={totalPendingRebate} precision={2} prefix="¥" valueStyle={{ color: 'var(--theme-primary)' }} /></Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small"><Statistic title="返利占比" value={totalBroughtRevenue > 0 ? (totalPaidRebate / totalBroughtRevenue) * 100 : 0} precision={1} suffix="%" /></Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
      <Col xs={24} lg={14}>
        <Card
          title="客户推荐链图谱"
          extra={
            <Space>
              <Select
                style={{ width: 200 }}
                placeholder="选择根节点客户"
                value={rootId}
                onChange={setRootId}
                showSearch
                filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                options={customers.map((c) => ({ value: c.id, label: c.xianyu_nickname }))}
              />
            </Space>
          }
        >
          {tree ? (
            <div style={{ height: 500, border: '1px solid var(--color-border)', borderRadius: 6, overflow: 'hidden' }}>
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView>
                <Background color="#f1f3f5" gap={16} />
                <Controls />
              </ReactFlow>
            </div>
          ) : (
            <Empty description="请选择根节点客户查看推荐链" />
          )}
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>
            图例：● 直接推荐（L1） ○ 间接推荐（L2+） · VIP/核心客户金色边框 · 连线金额=被介绍人累计成交
          </div>
        </Card>
      </Col>

      <Col xs={24} lg={10}>
        <Card
          title={<span><TrophyOutlined style={{ color: 'var(--color-warning)', marginRight: 8 }} />最佳介绍人排行榜</span>}
          extra={
            <Select
              size="small"
              value={sortBy}
              onChange={setSortBy}
              options={[
                { value: 'revenue', label: '按成交额' },
                { value: 'count', label: '按介绍人数' },
              ]}
            />
          }
        >
          {sortedRankings.length === 0 ? (
            <Empty description="暂无介绍数据" />
          ) : (
            <Table
              rowKey="referrerId"
              dataSource={sortedRankings}
              size="small"
              pagination={{ pageSize: 10 }}
              locale={{ emptyText: <Empty description="暂无排行数据" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              columns={[
                {
                  title: '排名',
                  width: 60,
                  render: (_: unknown, __: ReferrerRanking, idx: number) => (
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
                      {medals[idx] || idx + 1}
                    </span>
                  ),
                },
                {
                  title: '介绍人',
                  dataIndex: 'nickname',
                  render: (name: string, r: ReferrerRanking) => <a onClick={() => navigate(`/customers/${r.referrerId}`)}>{name}</a>,
                },
                { title: '介绍人数', dataIndex: 'introducedCount', width: 80, align: 'center' as const },
                { title: '成交额', dataIndex: 'broughtRevenue', width: 100, render: (v: number) => formatMoney(v), align: 'right' as const },
                { title: '待结算', dataIndex: 'pendingRebate', width: 90, render: (v: number) => <span style={{ color: 'var(--theme-primary)' }}>{formatMoney(v)}</span>, align: 'right' as const },
              ]}
            />
          )}
        </Card>
      </Col>
    </Row>
    </div>
  );
}
