import { useEffect, useState, useMemo } from 'react';
import { Card, Descriptions, Tag, Button, Space, Spin, Empty, Tabs, Table, Avatar, Row, Col, Statistic, Divider, message, Modal, Input, Switch, Tooltip } from 'antd';
import { ArrowLeftOutlined, EditOutlined, ShareAltOutlined, DollarOutlined, PlusOutlined, FileTextOutlined, StopOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import ReactFlow, { Background, Controls, type Node, type Edge, Handle, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import { getCustomer, updateCustomer, setCustomerTags } from '@/services/customerService';
import { listByCustomer } from '@/services/transactionService';
import { listAfterSales } from '@/services/afterSalesService';
import { getReferralTree, getReferrerRankings } from '@/services/referralService';
import { listByReferrer } from '@/services/rebateService';
import WarrantyTag from '@/components/WarrantyTag';
import { formatMoney, channelLabel, channelColorMap } from '@/utils/format';
import { formatDate, formatDateTime } from '@/utils/date';
import type { Customer, Transaction, AfterSales, ReferralTreeNode, RebateRecord, CustomerLevel, ChannelType } from '@/types';

const levelMap: Record<CustomerLevel, { label: string; color: string }> = {
  normal: { label: '普通', color: 'default' },
  vip: { label: 'VIP', color: 'gold' },
  core: { label: '核心', color: 'red' },
};

const tradeStatusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '待发货', color: 'blue' },
  completed: { label: '已完成', color: 'green' },
  aftersales: { label: '售后中', color: 'orange' },
  closed: { label: '已关闭', color: 'default' },
};

const aftersalesStatusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'red' },
  processing: { label: '处理中', color: 'orange' },
  resolved: { label: '已解决', color: 'green' },
  closed: { label: '已关闭', color: 'default' },
};

export default function CustomerDetail() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [trades, setTrades] = useState<Transaction[]>([]);
  const [afterSales, setAfterSales] = useState<AfterSales[]>([]);
  const [referralTree, setReferralTree] = useState<ReferralTreeNode | null>(null);
  const [rebates, setRebates] = useState<RebateRecord[]>([]);
  const [editOpen, setEditOpen] = useState(false);
  const [editNotes, setEditNotes] = useState('');
  const [editContact, setEditContact] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [tagInputVisible, setTagInputVisible] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const c = await getCustomer(Number(id));
      if (!c) {
        message.error('客户不存在');
        navigate('/customers');
        return;
      }
      setCustomer(c);
      setEditNotes(c.notes || '');
      setEditContact(c.contact_info || '');
      // 先查交易列表，再用交易 ID 批量查售后（避免重复查询与 N+1）
      const t = await listByCustomer(c.id!);
      const [allAfterSales, tree, rb] = await Promise.all([
        listAfterSales(),
        getReferralTree(c.id!),
        listByReferrer(c.id!),
      ]);
      const transactionIds = new Set(t.map((transaction) => transaction.id));
      setTrades(t.reverse());
      setAfterSales(allAfterSales.filter((ticket) => transactionIds.has(ticket.transaction_id)));
      setReferralTree(tree);
      setRebates(rb);
    } catch (err) {
      console.error('加载客户详情失败:', err);
      message.error(err instanceof Error ? err.message : '加载客户详情失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  if (!customer) return <Empty />;

  const totalRebate = rebates.reduce((s, r) => s + r.amount, 0);
  const pendingRebate = rebates.filter((r) => r.status === 'pending').reduce((s, r) => s + r.amount, 0);
  const avgTradeValue = trades.length > 0 ? customer.total_spent / trades.length : 0;
  const lastTradeAt = trades.length > 0 ? trades[0].trade_at : null;

  const handleSaveEdit = async () => {
    try {
      await updateCustomer(customer.id!, { notes: editNotes, contact_info: editContact });
      message.success('已保存');
      setEditOpen(false);
      loadData();
    } catch (err) {
      console.error('保存客户信息失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败，请重试');
    }
  };

  const handleAddTag = async () => {
    try {
      const tag = tagInput.trim();
      if (!tag) { setTagInputVisible(false); setTagInput(''); return; }
      if (customer.tags.includes(tag)) { message.warning('标签已存在'); return; }
      const newTags = [...customer.tags, tag];
      await setCustomerTags(customer.id!, newTags);
      setCustomer({ ...customer, tags: newTags });
      setTagInput('');
      setTagInputVisible(false);
      message.success('标签已添加');
    } catch (err) {
      console.error('添加标签失败:', err);
      message.error(err instanceof Error ? err.message : '添加标签失败，请重试');
    }
  };

  const handleRemoveTag = async (tag: string) => {
    try {
      const newTags = customer.tags.filter((t) => t !== tag);
      await setCustomerTags(customer.id!, newTags);
      setCustomer({ ...customer, tags: newTags });
      message.success('标签已移除');
    } catch (err) {
      console.error('移除标签失败:', err);
      message.error(err instanceof Error ? err.message : '移除标签失败，请重试');
    }
  };

  const handleBlacklistToggle = async (checked: boolean) => {
    setCustomer({ ...customer, is_blacklist: checked });
    try {
      await updateCustomer(customer.id!, { is_blacklist: checked });
      message.success(checked ? '已加入黑名单' : '已移出黑名单');
    } catch (err) {
      // 回滚乐观更新
      setCustomer(prev => prev ? { ...prev, is_blacklist: !prev.is_blacklist } : prev);
      console.error('黑名单切换失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const tradeColumns = [
    { title: '商品', dataIndex: 'product_name', ellipsis: true },
    { title: '渠道', dataIndex: 'channel', width: 70, render: (c: ChannelType) => <Tag color={channelColorMap[c] || 'default'}>{channelLabel(c)}</Tag> },
    { title: '售价', dataIndex: 'sale_price', width: 100, render: (v: number) => formatMoney(v), align: 'right' as const },
    { title: '利润', dataIndex: 'profit', width: 100, render: (v: number) => <span style={{ color: 'var(--color-success)' }}>{formatMoney(v)}</span>, align: 'right' as const },
    { title: '时间', dataIndex: 'trade_at', width: 140, render: (v: Date) => formatDate(v) },
    { title: '状态', dataIndex: 'status', width: 90, render: (s: string) => <Tag color={tradeStatusMap[s]?.color || 'default'}>{tradeStatusMap[s]?.label || s}</Tag> },
    { title: '质保', width: 100, render: (_: unknown, r: Transaction) => <WarrantyTag warrantyEnd={r.warranty_end} status={r.status} /> },
    { title: '操作', width: 80, render: (_: unknown, r: Transaction) => <Button type="link" size="small" onClick={() => navigate(`/transactions/${r.id}`)}>详情</Button> },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} />
        <span style={{ fontSize: 18, fontWeight: 600 }}>客户详情</span>
      </Space>

      <Row gutter={16}>
        <Col xs={24} lg={8}>
          <Card>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <Avatar size={64} style={{ background: customer.level === 'core' ? 'var(--color-danger)' : customer.level === 'vip' ? 'var(--color-warning)' : 'var(--color-info)' }}>
                {customer.xianyu_nickname.charAt(0)}
              </Avatar>
              <div style={{ fontSize: 18, fontWeight: 600, marginTop: 12 }}>{customer.xianyu_nickname}</div>
              <div style={{ marginTop: 4 }}>
                <Tag color={levelMap[customer.level].color}>{levelMap[customer.level].label}</Tag>
                {customer.is_blacklist && <Tag color="red">黑名单</Tag>}
              </div>
            </div>
            <Statistic title="累计消费" value={customer.total_spent} precision={2} prefix="¥" valueStyle={{ color: 'var(--theme-primary)' }} />
            <Statistic title="交易笔数" value={customer.trade_count} style={{ marginTop: 12 }} />
            <Divider style={{ margin: '12px 0' }} />
            <Descriptions column={1} size="small">
              <Descriptions.Item label="首次交易">{customer.first_trade_at ? formatDate(customer.first_trade_at) : '-'}</Descriptions.Item>
              <Descriptions.Item label="联系方式">{customer.contact_info || '-'}</Descriptions.Item>
              <Descriptions.Item label="黑名单">
                <Switch size="small" checked={customer.is_blacklist} onChange={handleBlacklistToggle} />
                <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>
                  {customer.is_blacklist ? '已拉黑' : '正常'}
                </span>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 8 }}>
              {customer.tags.map((t) => (
                <Tag key={t} closable onClose={() => handleRemoveTag(t)} style={{ marginBottom: 4 }}>
                  {t}
                </Tag>
              ))}
              {tagInputVisible ? (
                <Input
                  size="small"
                  style={{ width: 100 }}
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onPressEnter={handleAddTag}
                  onBlur={() => { setTagInputVisible(false); setTagInput(''); }}
                />
              ) : (
                <Tag onClick={() => setTagInputVisible(true)} style={{ borderStyle: 'dashed', cursor: 'pointer' }}>
                  <PlusOutlined /> 添加标签
                </Tag>
              )}
            </div>
            <Space direction="vertical" style={{ width: '100%', marginTop: 12 }}>
              <Button block type="primary" icon={<PlusOutlined />} onClick={() => navigate(`/transactions/new?customerId=${customer.id}`)}>
                新建交易
              </Button>
              <Button block icon={<EditOutlined />} onClick={() => setEditOpen(true)}>编辑客户</Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Card>
            <Tabs
              items={[
                {
                  key: 'overview',
                  label: '概览',
                  children: (
                    <div>
                      <Row gutter={16}>
                        <Col span={6}>
                          <Statistic title="累计消费" value={customer.total_spent} precision={2} prefix="¥" />
                        </Col>
                        <Col span={6}>
                          <Statistic title="交易笔数" value={customer.trade_count} />
                        </Col>
                        <Col span={6}>
                          <Statistic title="客单价" value={avgTradeValue} precision={2} prefix="¥" />
                        </Col>
                        <Col span={6}>
                          <Statistic title="客户等级" value={levelMap[customer.level].label} />
                        </Col>
                      </Row>
                      <Row gutter={16} style={{ marginTop: 16 }}>
                        <Col span={6}>
                          <Statistic title="首次交易" value={customer.first_trade_at ? formatDate(customer.first_trade_at) : '-'} />
                        </Col>
                        <Col span={6}>
                          <Statistic title="最近交易" value={lastTradeAt ? formatDate(lastTradeAt) : '-'} />
                        </Col>
                        <Col span={6}>
                          <Statistic title="成功介绍" value={referralTree?.children.length || 0} suffix="人" />
                        </Col>
                        <Col span={6}>
                          <Statistic title="待结算返利" value={pendingRebate} precision={2} prefix="¥" />
                        </Col>
                      </Row>
                      <Divider orientation="left">推荐成果</Divider>
                      <Row gutter={16}>
                        <Col span={8}>
                          <Statistic title="带来成交" value={referralTree?.children.reduce((s, c) => s + c.totalRevenue, 0) || 0} precision={2} prefix="¥" />
                        </Col>
                        <Col span={8}>
                          <Statistic title="累计返利" value={totalRebate} precision={2} prefix="¥" />
                        </Col>
                        <Col span={8}>
                          <Statistic title="售后次数" value={afterSales.length} suffix="次" />
                        </Col>
                      </Row>
                      <Button type="link" icon={<ShareAltOutlined />} onClick={() => navigate(`/referral?customerId=${customer.id}`)}>查看推荐树</Button>
                      {customer.notes && (
                        <>
                          <Divider orientation="left">备注</Divider>
                          <div style={{ padding: 12, background: 'var(--color-bg)', borderRadius: 6, whiteSpace: 'pre-wrap' }}>{customer.notes}</div>
                        </>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'trades',
                  label: `交易记录 (${trades.length})`,
                  children: <Table rowKey="id" dataSource={trades} columns={tradeColumns} size="small" pagination={{ pageSize: 10 }} locale={{ emptyText: <Empty description="暂无交易" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} />,
                },
                {
                  key: 'referral',
                  label: '推荐链',
                  children: referralTree && referralTree.children.length > 0 ? (
                    <InlineReferralGraph node={referralTree} navigate={navigate} />
                  ) : <Empty description="暂无推荐记录" />,
                },
                {
                  key: 'aftersales',
                  label: `售后记录 (${afterSales.length})`,
                  children: afterSales.length > 0 ? (
                    <Table
                      rowKey="id"
                      dataSource={afterSales}
                      size="small"
                      pagination={{ pageSize: 10 }}
                      columns={[
                        { title: '问题描述', dataIndex: 'issue_desc', ellipsis: true },
                        { title: '状态', dataIndex: 'status', width: 90, render: (s: string) => <Tag color={aftersalesStatusMap[s]?.color || 'default'}>{aftersalesStatusMap[s]?.label || s}</Tag> },
                        { title: '创建时间', dataIndex: 'created_at', width: 140, render: (v: Date) => formatDate(v) },
                      ]}
                    />
                  ) : <Empty description="暂无售后记录" />,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Modal title="编辑客户" open={editOpen} onCancel={() => setEditOpen(false)} onOk={handleSaveEdit} okText="保存">
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}>联系方式</div>
          <Input value={editContact} onChange={(e) => setEditContact(e.target.value)} placeholder="微信/手机号" />
        </div>
        <div>
          <div style={{ marginBottom: 4 }}>备注</div>
          <Input.TextArea rows={4} value={editNotes} onChange={(e) => setEditNotes(e.target.value)} placeholder="客户备注" />
        </div>
      </Modal>
    </div>
  );
}

// 推荐链内嵌图谱（P3-4 升级：从文本树升级为 ReactFlow 可视化）
// 复用 global.css 中的 .referral-node 样式，与 ReferralGraph 页面保持一致
// 节点点击跳转客户详情；图谱容器固定高度 400px，超出可缩放/拖拽查看
function InlineReferralGraph({ node, navigate }: { node: ReferralTreeNode; navigate: (path: string) => void }) {
  const { nodes, edges } = useMemo(() => {
    const ns: Node[] = [];
    const es: Edge[] = [];
    // 简化的树状布局：自顶向下，子节点按序横向排列
    const layout = (n: ReferralTreeNode, x: number, y: number): number => {
      ns.push({
        id: String(n.id),
        type: 'referral',
        position: { x, y },
        data: { name: n.name, revenue: n.totalRevenue, level: n.level, isVip: false },
      });
      if (n.children.length === 0) return x + 140;
      let childX = x;
      const childY = y + 110;
      for (const child of n.children) {
        const endX = layout(child, childX, childY);
        es.push({
          id: `${n.id}-${child.id}`,
          source: String(n.id),
          target: String(child.id),
          animated: true,
          label: formatMoney(child.totalRevenue),
          style: { stroke: 'var(--theme-primary)', strokeWidth: 2 },
        });
        childX = endX + 60;
      }
      return childX - 60;
    };
    layout(node, 0, 0);
    return { nodes: ns, edges: es };
  }, [node]);

  const nodeTypes = useMemo(() => ({
    referral: ({ data }: { data: { name: string; revenue: number; level: number; isVip: boolean } }) => (
      <div
        className={`referral-node ${data.isVip ? 'vip' : ''}`}
        style={{ cursor: 'pointer' }}
        title="点击查看客户详情"
      >
        <Handle type="target" position={Position.Top} />
        <div className="node-name">{data.name}</div>
        <div className="node-revenue">{formatMoney(data.revenue)}</div>
        {data.level > 0 && <div style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>L{data.level}</div>}
        <Handle type="source" position={Position.Bottom} />
      </div>
    ),
  }), []);

  return (
    <div>
      <div style={{ height: 400, border: '1px solid var(--color-border)', borderRadius: 6, overflow: 'hidden' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, n) => navigate(`/customers/${n.id}`)}
        >
          <Background color="var(--color-border-light, #f1f3f5)" gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>
        图例：节点显示客户昵称与累计成交额 · 连线金额=被介绍人累计成交 · 点击节点查看客户详情 · 可缩放拖拽
      </div>
    </div>
  );
}
