import { useEffect, useState, useCallback, useMemo } from 'react';
import { Card, Table, Button, Space, Tag, Modal, Input, Select, message, Row, Col, Statistic, Empty, Tabs, DatePicker, Popconfirm, Result } from 'antd';
import { PlusOutlined, SearchOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { listAfterSales, createAfterSales, updateStatus, deleteAfterSales, getAfterSalesStats, getTopIssueProducts } from '@/services/afterSalesService';
import { listTransactions } from '@/services/transactionService';
import AttachmentUpload from '@/components/AttachmentUpload';
import { formatDateTime } from '@/utils/date';
import { formatPercent } from '@/utils/format';
import { clampPageForRecordCount, getPageForRecordId } from '@/utils/pagination';
import type { AfterSales, Transaction, AfterSalesStatus, SolutionType } from '@/types';

const { TextArea } = Input;
const PAGE_SIZE = 20;

const statusMap: Record<AfterSalesStatus, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'red' },
  processing: { label: '处理中', color: 'orange' },
  resolved: { label: '已解决', color: 'green' },
  closed: { label: '已关闭', color: 'default' },
};

const solutionMap: Record<SolutionType, string> = {
  remote: '远程协助',
  reship: '重新发货',
  refund: '退款',
  other: '其他',
};

function getAfterSalesOverdueHours(ticket: AfterSales): number {
  if (ticket.status !== 'pending' && ticket.status !== 'processing') return 0;
  const threshold = ticket.status === 'pending' ? 24 : 48;
  const elapsed = dayjs().diff(dayjs(ticket.created_at), 'hour');
  return elapsed > threshold ? elapsed : 0;
}

export default function AfterSalesList() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const focusedTicketId = Number(searchParams.get('ticketId') || 0);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<AfterSales[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [keyword, setKeyword] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [transactions, setTransactions] = useState<Map<number, Transaction>>(new Map());
  const [customers, setCustomers] = useState<Map<number, string>>(new Map());
  const [createOpen, setCreateOpen] = useState(false);
  const [resolveOpen, setResolveOpen] = useState(false);
  const [current, setCurrent] = useState<AfterSales | null>(null);
  const [createForm, setCreateForm] = useState({ transaction_id: undefined as number | undefined, issue_desc: '', attachments: [] as string[] });
  const [resolveForm, setResolveForm] = useState<{ type?: SolutionType; desc: string }>({ desc: '' });
  const [stats, setStats] = useState<{ totalCount: number; pendingCount: number; resolvedCount: number; avgDurationHours: number; rate: number } | null>(null);
  const [topIssues, setTopIssues] = useState<{ productName: string; count: number }[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [list, trades, st, issues] = await Promise.all([
        listAfterSales(),
        listTransactions(),
        getAfterSalesStats(),
        getTopIssueProducts(5),
      ]);
      const tMap = new Map<number, Transaction>();
      trades.forEach((t) => tMap.set(t.id!, t));
      setTransactions(tMap);
      // 用交易内联返回的 customer_name 构建客户名映射（避免本地 db 直访）
      const cMap = new Map<number, string>();
      trades.forEach((t) => {
        const name = (t as any).customer_name as string | undefined;
        if (name) cMap.set(t.customer_id, name);
      });
      setCustomers(cMap);
      setData(list);
      setStats(st);
      setTopIssues(issues);
    } catch (err) {
      console.error('加载售后列表失败:', err);
      setLoadError(true);
      message.error(err instanceof Error ? err.message : '加载售后列表失败，请重试');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!focusedTicketId || data.length === 0) return;
    const ticket = data.find((item) => item.id === focusedTicketId);
    if (!ticket) return;
    setStatusFilter('all');
    setKeyword('');
    setDateRange(null);
  }, [focusedTicketId, data]);

  const handleCreate = async () => {
    if (!createForm.transaction_id || !createForm.issue_desc.trim()) {
      message.error('请选择交易并填写问题描述');
      return;
    }
    try {
      await createAfterSales({ transaction_id: createForm.transaction_id, issue_desc: createForm.issue_desc, attachments: createForm.attachments });
      message.success('售后工单已创建');
      setCreateOpen(false);
      setCreateForm({ transaction_id: undefined, issue_desc: '', attachments: [] });
      loadData();
    } catch (err) {
      console.error('创建售后工单失败:', err);
      message.error(err instanceof Error ? err.message : '创建售后工单失败，请重试');
    }
  };

  const handleResolve = async () => {
    if (!current) return;
    try {
      const solution = resolveForm.type ? { type: resolveForm.type, desc: resolveForm.desc } : undefined;
      await updateStatus(current.id!, 'resolved', solution);
      message.success('已标记为已解决');
      setResolveOpen(false);
      setResolveForm({ desc: '' });
      setCurrent(null);
      loadData();
    } catch (err) {
      console.error('标记售后已解决失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败，请重试');
    }
  };

  const handleStatusChange = async (id: number, status: AfterSalesStatus) => {
    try {
      await updateStatus(id, status);
      message.success('状态已更新');
      loadData();
    } catch (err) {
      console.error('更新售后状态失败:', err);
      message.error(err instanceof Error ? err.message : '状态更新失败，请重试');
    }
  };

  // P1：软删除工单（移入回收站，30 天内可恢复）
  const handleDelete = async (id: number) => {
    try {
      await deleteAfterSales(id);
      message.success('工单已移入回收站');
      loadData();
    } catch (err) {
      console.error('删除售后工单失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败，请重试');
    }
  };

  const columns = [
    {
      title: '工单',
      dataIndex: 'id',
      width: 70,
      render: (id: number) => (
        <Space size={4}>
          <span>#{id}</span>
          {id === focusedTicketId && <Tag color="gold">定位</Tag>}
        </Space>
      ),
    },
    {
      title: '关联交易',
      dataIndex: 'transaction_id',
      width: 180,
      render: (tid: number) => {
        const t = transactions.get(tid);
        return t ? (
          <a onClick={() => navigate(`/transactions/${tid}`)}>{t.product_name}</a>
        ) : `交易#${tid}`;
      },
    },
    {
      title: '客户',
      width: 100,
      render: (_: unknown, r: AfterSales) => {
        const t = transactions.get(r.transaction_id);
        const c = t ? customers.get(t.customer_id) : undefined;
        return c || '-';
      },
    },
    {
      title: '问题描述',
      dataIndex: 'issue_desc',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: AfterSalesStatus) => <Tag color={statusMap[s].color}>{statusMap[s].label}</Tag>,
    },
    {
      title: '跟进',
      width: 110,
      render: (_: unknown, r: AfterSales) => {
        const overdueHours = getAfterSalesOverdueHours(r);
        return overdueHours > 0 ? <Tag color="red">超时 {overdueHours}h</Tag> : <span style={{ color: 'var(--color-text-tertiary)' }}>-</span>;
      },
    },
    {
      title: '解决方式',
      dataIndex: 'solution_type',
      width: 100,
      render: (s?: SolutionType) => (s ? solutionMap[s] : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 140,
      render: (v: Date) => formatDateTime(v),
    },
    {
      title: '耗时',
      dataIndex: 'duration_hours',
      width: 80,
      render: (v?: number) => (v !== undefined ? `${v}h` : '-'),
    },
    {
      title: '操作',
      width: 240,
      render: (_: unknown, r: AfterSales) => (
        <Space size={4}>
          {r.status === 'pending' && (
            <Button size="small" type="primary" onClick={() => handleStatusChange(r.id!, 'processing')}>开始处理</Button>
          )}
          {(r.status === 'pending' || r.status === 'processing') && (
            <Button size="small" onClick={() => { setCurrent(r); setResolveOpen(true); }}>解决</Button>
          )}
          {r.status !== 'closed' && r.status !== 'resolved' && (
            <Button size="small" onClick={() => handleStatusChange(r.id!, 'closed')}>关闭</Button>
          )}
          <Popconfirm
            title="删除后工单将移入回收站"
            description="30 天内可在「设置 - 回收站」恢复"
            okText="删除"
            okType="danger"
            onConfirm={() => handleDelete(r.id!)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const filteredData = useMemo(() => data.filter((a) => {
    if (statusFilter === 'overdue') {
      if (getAfterSalesOverdueHours(a) === 0) return false;
    } else if (statusFilter !== 'all' && a.status !== statusFilter) {
      return false;
    }
    if (dateRange) {
      const created = dayjs(a.created_at);
      if (created.isBefore(dateRange[0], 'day') || created.isAfter(dateRange[1], 'day')) return false;
    }
    if (keyword.trim()) {
      const lower = keyword.trim().toLowerCase();
      const t = transactions.get(a.transaction_id);
      const c = t ? customers.get(t.customer_id) : undefined;
      const haystack = [a.issue_desc, t?.product_name, c].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(lower)) return false;
    }
    return true;
  }), [data, statusFilter, dateRange, keyword, transactions, customers]);

  const statusCounts = useMemo(() => {
    const m: Record<string, number> = { pending: 0, processing: 0, resolved: 0, closed: 0 };
    for (const a of data) m[a.status] = (m[a.status] || 0) + 1;
    return m;
  }, [data]);
  const countByStatus = (s: AfterSalesStatus) => statusCounts[s] || 0;
  const overdueCount = useMemo(() => data.filter((a) => getAfterSalesOverdueHours(a) > 0).length, [data]);

  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, keyword, dateRange]);

  useEffect(() => {
    if (!focusedTicketId) return;
    setCurrentPage((page) => getPageForRecordId(filteredData, focusedTicketId, PAGE_SIZE, page));
  }, [focusedTicketId, filteredData]);

  useEffect(() => {
    setCurrentPage((page) => clampPageForRecordCount(filteredData.length, PAGE_SIZE, page));
  }, [filteredData.length]);

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card><Statistic title="售后总数" value={stats?.totalCount || 0} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="待处理" value={stats?.pendingCount || 0} valueStyle={{ color: 'var(--color-danger)' }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="超时未完成" value={overdueCount} valueStyle={{ color: 'var(--color-danger)' }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="售后率" value={formatPercent(stats?.rate || 0)} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="平均处理时长" value={stats?.avgDurationHours || 0} suffix="小时" /></Card>
        </Col>
      </Row>

      <Card
        title="售后工单"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>创建工单</Button>}
      >
        {loadError ? (
          <Result
            status="error"
            title="加载失败"
            subTitle="无法加载售后数据，可能是浏览器存储异常或被占用"
            extra={[
              <Button key="retry" type="primary" icon={<ReloadOutlined />} onClick={() => loadData()}>重试</Button>,
            ]}
          />
        ) : (
          <>
        <Tabs
          activeKey={statusFilter}
          onChange={setStatusFilter}
          items={[
            { key: 'all', label: `全部 (${data.length})` },
            { key: 'overdue', label: <span style={{ color: 'var(--color-danger)' }}>超时 ({overdueCount})</span> },
            { key: 'pending', label: <span style={{ color: 'var(--color-danger)' }}>待处理 ({countByStatus('pending')})</span> },
            { key: 'processing', label: <span style={{ color: 'var(--theme-primary)' }}>处理中 ({countByStatus('processing')})</span> },
            { key: 'resolved', label: <span style={{ color: 'var(--color-success)' }}>已解决 ({countByStatus('resolved')})</span> },
            { key: 'closed', label: `已关闭 (${countByStatus('closed')})` },
          ]}
          style={{ marginBottom: 16 }}
        />
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={10}>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索问题描述 / 商品名称 / 客户昵称"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </Col>
          <Col xs={24} sm={10}>
            <DatePicker.RangePicker
              style={{ width: '100%' }}
              value={dateRange}
              onChange={(v) => setDateRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
              placeholder={['创建开始', '创建结束']}
            />
          </Col>
          <Col xs={24} sm={4}>
            <Button
              block
              onClick={() => { setKeyword(''); setDateRange(null); }}
              disabled={!keyword && !dateRange}
            >重置</Button>
          </Col>
        </Row>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={filteredData}
          columns={columns}
          size="middle"
          onRow={(record) => ({
            style: record.id === focusedTicketId ? { background: 'var(--color-warning-light)' } : undefined,
          })}
          locale={{
            emptyText: data.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span>
                    暂无售后记录
                    <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                      创建工单
                    </Button>
                  </span>
                }
              />
            ) : (
              <Empty description="未匹配到符合条件的售后记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ),
          }}
          pagination={{
            current: currentPage,
            pageSize: PAGE_SIZE,
            onChange: (page) => setCurrentPage(page),
          }}
        />
          </>
        )}
      </Card>

      {topIssues.length > 0 && (
        <Card title="高频问题商品 TOP5" style={{ marginTop: 16 }}>
          {topIssues.map((i, idx) => (
            <div key={i.productName} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
              <span>{idx + 1}. {i.productName}</span>
              <Tag color="orange">{i.count} 次</Tag>
            </div>
          ))}
        </Card>
      )}

      <Modal title="创建售后工单" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={handleCreate} okText="创建">
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}>关联交易</div>
          <Select
            style={{ width: '100%' }}
            placeholder="选择交易"
            value={createForm.transaction_id}
            onChange={(v) => setCreateForm({ ...createForm, transaction_id: v })}
            showSearch
            filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
            options={Array.from(transactions.values()).map((t) => ({ value: t.id, label: `${t.product_name} - ${formatDateTime(t.trade_at)}` }))}
          />
        </div>
        <div>
          <div style={{ marginBottom: 4 }}>问题描述</div>
          <TextArea rows={4} value={createForm.issue_desc} onChange={(e) => setCreateForm({ ...createForm, issue_desc: e.target.value })} placeholder="描述客户反馈的问题" />
        </div>
        <div style={{ marginTop: 12 }}>
          <div style={{ marginBottom: 4 }}>问题截图/附件</div>
          <AttachmentUpload
            value={createForm.attachments}
            onChange={(ids) => setCreateForm({ ...createForm, attachments: ids })}
            maxCount={6}
          />
        </div>
      </Modal>

      <Modal title="标记为已解决" open={resolveOpen} onCancel={() => setResolveOpen(false)} onOk={handleResolve} okText="确认解决">
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}>解决方式</div>
          <Select
            style={{ width: '100%' }}
            placeholder="选择解决方式"
            value={resolveForm.type}
            onChange={(v) => setResolveForm({ ...resolveForm, type: v })}
            options={(Object.keys(solutionMap) as SolutionType[]).map((k) => ({ value: k, label: solutionMap[k] }))}
          />
        </div>
        <div>
          <div style={{ marginBottom: 4 }}>解决说明</div>
          <TextArea rows={3} value={resolveForm.desc} onChange={(e) => setResolveForm({ ...resolveForm, desc: e.target.value })} placeholder="选填" />
        </div>
      </Modal>
    </div>
  );
}
