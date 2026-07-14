import { useEffect, useState, useCallback } from 'react';
import { Card, Table, Button, Space, Input, Select, DatePicker, Tag, Popconfirm, message, Row, Col, Dropdown, Segmented, Empty, Switch, Tooltip, Modal, Result } from 'antd';
import { PlusOutlined, ExportOutlined, DeleteOutlined, EditOutlined, EyeOutlined, DownOutlined, ClockCircleOutlined, CustomerServiceOutlined, CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { listTransactions, softDeleteTransaction, changeStatus } from '@/services/transactionService';
import { createAfterSales } from '@/services/afterSalesService';
import { getCustomer } from '@/services/customerService';
import { exportTransactionsCSV, downloadFile } from '@/utils/export';
import { formatMoney, channelLabel, channelColorMap } from '@/utils/format';
import { formatDate } from '@/utils/date';
import { filterTransactions } from '@/utils/transactionFilter';
import WarrantyTag from '@/components/WarrantyTag';
import { useAppStore } from '@/store/useAppStore';
import type { Transaction, TransactionStatus, ChannelType } from '@/types';

const { RangePicker } = DatePicker;

const statusMap: Record<TransactionStatus, { label: string; color: string }> = {
  pending: { label: '待发货', color: 'blue' },
  completed: { label: '已完成', color: 'green' },
  aftersales: { label: '售后中', color: 'orange' },
  closed: { label: '已关闭', color: 'default' },
};

export default function TransactionList() {
  const navigate = useNavigate();
  const { refreshAll } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Transaction[]>([]);
  const [customers, setCustomers] = useState<Map<number, string>>(new Map());
  const [filtered, setFiltered] = useState<Transaction[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [keyword, setKeyword] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [timeFilter, setTimeFilter] = useState<'all' | 'today' | 'week' | 'month'>('all');
  const [warrantyUrgentOnly, setWarrantyUrgentOnly] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<number[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [asOpen, setAsOpen] = useState(false);
  const [asTransaction, setAsTransaction] = useState<Transaction | null>(null);
  const [asDesc, setAsDesc] = useState('');
  const [asLoading, setAsLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const list = await listTransactions();
      // 用后端内联返回的 customer_name 构建客户名映射（避免 N+1 查询与本地 db 直访）
      const map = new Map<number, string>();
      list.forEach((t) => {
        const name = t.customer_name;
        if (name) map.set(t.customer_id, name);
      });
      setCustomers(map);
      // 按时间倒序
      list.sort((a, b) => new Date(b.trade_at).getTime() - new Date(a.trade_at).getTime());
      setData(list);
      setFiltered(list);
    } catch (err) {
      console.error('加载交易列表失败:', err);
      setLoadError(true);
      message.error(err instanceof Error ? err.message : '加载交易列表失败，请重试');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 筛选（逻辑提取至 filterTransactions 纯函数，便于单元测试）
  useEffect(() => {
    const result = filterTransactions(data, {
      statusFilter,
      channelFilter,
      keyword,
      dateRange,
      timeFilter,
      warrantyUrgentOnly,
      customers,
    });
    setFiltered(result);
    setPage(1);
  }, [data, statusFilter, channelFilter, keyword, dateRange, customers, timeFilter, warrantyUrgentOnly]);

  const handleDelete = async (id: number) => {
    try {
      await softDeleteTransaction(id);
      message.success('已删除');
      refreshAll();
      loadData();
    } catch (err) {
      console.error('删除交易失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败，请重试');
    }
  };

  const handleExport = () => {
    const target = selectedKeys.length > 0 ? filtered.filter((t) => selectedKeys.includes(t.id!)) : filtered;
    const csv = exportTransactionsCSV(target);
    downloadFile(csv, `交易明细_${dayjs().format('YYYYMMDD_HHmmss')}.csv`, 'text/csv');
    message.success(`已导出 ${target.length} 条记录`);
  };

  const handleBatchStatus = async (status: TransactionStatus) => {
    if (selectedKeys.length === 0) return;
    setBatchLoading(true);
    try {
      for (const id of selectedKeys) {
        await changeStatus(id as number, status);
      }
      message.success(`已批量更新 ${selectedKeys.length} 条交易状态`);
      setSelectedKeys([]);
      loadData();
    } catch {
      message.error('批量更新失败');
    } finally {
      setBatchLoading(false);
    }
  };

  const handleMarkAfterSales = (t: Transaction) => {
    setAsTransaction(t);
    setAsDesc('');
    setAsOpen(true);
  };

  const handleCreateAfterSales = async () => {
    if (!asTransaction) return;
    if (!asDesc.trim()) {
      message.warning('请输入问题描述');
      return;
    }
    setAsLoading(true);
    try {
      await createAfterSales({
        transaction_id: asTransaction.id!,
        issue_desc: asDesc.trim(),
      });
      message.success('已创建售后工单');
      setAsOpen(false);
      setAsTransaction(null);
      setAsDesc('');
      loadData();
    } catch (err) {
      console.error('创建售后工单失败:', err);
      message.error(err instanceof Error ? err.message : '创建失败');
    } finally {
      setAsLoading(false);
    }
  };

  const handleContact = async (customerId: number) => {
    // 懒加载客户完整信息（联系方式不在列表内联，按需获取）
    const c = await getCustomer(customerId);
    if (!c) return;
    if (!c.contact_info) {
      message.warning('该客户未填写联系方式');
      return;
    }
    try {
      await navigator.clipboard.writeText(c.contact_info);
      message.success(`联系方式已复制：${c.contact_info}`);
    } catch {
      message.error('复制失败，请手动复制');
    }
  };

  const columns = [
    {
      title: '订单号',
      dataIndex: 'xianyu_order_no',
      width: 140,
      render: (v: string) => v || <span style={{ color: 'var(--color-text-tertiary)' }}>-</span>,
    },
    {
      title: '渠道',
      dataIndex: 'channel',
      width: 70,
      render: (c: ChannelType) => <Tag color={channelColorMap[c] || 'default'}>{channelLabel(c)}</Tag>,
    },
    {
      title: '商品名称',
      dataIndex: 'product_name',
      ellipsis: true,
    },
    {
      title: '售价',
      dataIndex: 'sale_price',
      width: 100,
      sorter: (a: Transaction, b: Transaction) => a.sale_price - b.sale_price,
      render: (v: number) => <span className="tabular-nums">{formatMoney(v)}</span>,
      align: 'right' as const,
    },
    {
      title: '利润',
      dataIndex: 'profit',
      width: 100,
      sorter: (a: Transaction, b: Transaction) => a.profit - b.profit,
      render: (v: number) => <span className="tabular-nums" style={{ color: v >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>{formatMoney(v)}</span>,
      align: 'right' as const,
    },
    {
      title: '买家',
      dataIndex: 'customer_id',
      width: 120,
      render: (id: number) => {
        const name = customers.get(id);
        return name ? (
          <a onClick={() => navigate(`/customers/${id}`)}>{name}</a>
        ) : '-';
      },
    },
    {
      title: '交易时间',
      dataIndex: 'trade_at',
      width: 150,
      sorter: (a: Transaction, b: Transaction) => new Date(a.trade_at).getTime() - new Date(b.trade_at).getTime(),
      render: (v: Date) => formatDate(v, 'YYYY-MM-DD HH:mm'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (s: TransactionStatus) => <Tag color={statusMap[s].color}>{statusMap[s].label}</Tag>,
    },
    {
      title: '质保',
      width: 100,
      render: (_: unknown, r: Transaction) => <WarrantyTag warrantyEnd={r.warranty_end} status={r.status} />,
    },
    {
      title: '操作',
      width: 200,
      fixed: 'right' as const,
      render: (_: unknown, r: Transaction) => (
        <Space size={0}>
          <Tooltip title="详情"><Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/transactions/${r.id}`)} /></Tooltip>
          <Tooltip title="编辑"><Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/transactions/${r.id}/edit`)} /></Tooltip>
          <Tooltip title="标记售后"><Button type="link" size="small" icon={<CustomerServiceOutlined />} onClick={() => handleMarkAfterSales(r)} /></Tooltip>
          <Tooltip title="复制联系方式"><Button type="link" size="small" icon={<CopyOutlined />} onClick={() => handleContact(r.customer_id)} /></Tooltip>
          <Popconfirm title="确认删除该交易？" onConfirm={() => handleDelete(r.id!)} okText="删除" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="交易管理"
      extra={
        <Space>
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/transactions/new')}>记一笔</Button>
        </Space>
      }
    >
      {loadError ? (
        <Result
          status="error"
          title="加载失败"
          subTitle="无法加载交易列表，可能是浏览器存储异常或被占用"
          extra={[
            <Button key="retry" type="primary" icon={<ReloadOutlined />} onClick={() => loadData()}>重试</Button>,
          ]}
        />
      ) : (
        <>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Input.Search placeholder="搜索商品名/订单号/买家昵称" allowClear value={keyword} onChange={(e) => setKeyword(e.target.value)} />
        </Col>
        <Col xs={12} sm={4}>
          <Select
            style={{ width: '100%' }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'pending', label: '待发货' },
              { value: 'completed', label: '已完成' },
              { value: 'aftersales', label: '售后中' },
              { value: 'closed', label: '已关闭' },
            ]}
          />
        </Col>
        <Col xs={12} sm={4}>
          <Select
            style={{ width: '100%' }}
            value={channelFilter}
            onChange={setChannelFilter}
            options={[
              { value: 'all', label: '全部渠道' },
              { value: 'xianyu', label: '闲鱼' },
              { value: 'wechat', label: '微信' },
              { value: 'other', label: '其他' },
            ]}
          />
        </Col>
        <Col xs={24} sm={8}>
          <RangePicker style={{ width: '100%' }} value={dateRange} onChange={(v) => setDateRange(v as any)} />
        </Col>
        <Col xs={24} sm={6}>
          <Segmented
            value={timeFilter}
            onChange={(v) => setTimeFilter(v as typeof timeFilter)}
            options={[
              { label: '全部', value: 'all' },
              { label: '今天', value: 'today' },
              { label: '本周', value: 'week' },
              { label: '本月', value: 'month' },
            ]}
            size="middle"
          />
        </Col>
        <Col xs={24} sm={6}>
          <Tooltip title="仅显示质保3天内即将到期的交易">
            <Switch
              checked={warrantyUrgentOnly}
              onChange={setWarrantyUrgentOnly}
              checkedChildren={<ClockCircleOutlined />}
              unCheckedChildren="质保到期"
            />
            <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>仅看即将到期</span>
          </Tooltip>
        </Col>
      </Row>

      {selectedKeys.length > 0 && (
        <Space style={{ marginBottom: 16 }}>
          <span>已选 {selectedKeys.length} 项</span>
          <Dropdown
            menu={{
              items: [
                { key: 'pending', label: '待发货', onClick: () => handleBatchStatus('pending') },
                { key: 'completed', label: '已完成', onClick: () => handleBatchStatus('completed') },
                { key: 'aftersales', label: '售后中', onClick: () => handleBatchStatus('aftersales') },
                { key: 'closed', label: '已关闭', onClick: () => handleBatchStatus('closed') },
              ],
            }}
          >
            <Button loading={batchLoading} icon={<DownOutlined />}>批量标记状态</Button>
          </Dropdown>
        </Space>
      )}

      <Table
        rowKey="id"
        loading={loading}
        dataSource={filtered.slice((page - 1) * pageSize, page * pageSize)}
        columns={columns}
        scroll={{ x: 1170 }}
        size="middle"
        locale={{
          emptyText: data.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  暂无交易记录
                  <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => navigate('/transactions/new')}>
                    立即记一笔
                  </Button>
                </span>
              }
            />
          ) : (
            <Empty description="未匹配到符合条件的交易" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ),
        }}
        rowSelection={{
          selectedRowKeys: selectedKeys,
          onChange: (keys) => setSelectedKeys(keys as number[]),
        }}
        pagination={{
          current: page,
          pageSize,
          total: filtered.length,
          showSizeChanger: true,
          pageSizeOptions: ['20', '50', '100'],
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showTotal: (t) => `共 ${t} 条`,
        }}
      />

      <Modal
        title="创建售后工单"
        open={asOpen}
        onCancel={() => { setAsOpen(false); setAsTransaction(null); setAsDesc(''); }}
        onOk={handleCreateAfterSales}
        confirmLoading={asLoading}
        okText="创建"
        cancelText="取消"
      >
        {asTransaction && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--color-bg-secondary)', borderRadius: 8 }}>
            <div><strong>商品：</strong>{asTransaction.product_name}</div>
            <div><strong>订单号：</strong>{asTransaction.xianyu_order_no || '-'}</div>
          </div>
        )}
        <Input.TextArea
          rows={4}
          placeholder="请描述售后问题..."
          value={asDesc}
          onChange={(e) => setAsDesc(e.target.value)}
          maxLength={500}
          showCount
        />
      </Modal>
        </>
      )}
    </Card>
  );
}
