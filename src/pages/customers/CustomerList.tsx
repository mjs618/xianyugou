import { useEffect, useState, useCallback, useMemo } from 'react';
import { Card, Table, Button, Space, Input, Tabs, Tag, Avatar, Popconfirm, message, Tooltip, Select, Empty, Modal, Form, Result } from 'antd';
import { PlusOutlined, EditOutlined, EyeOutlined, StopOutlined, CheckCircleOutlined, ExportOutlined, DeleteOutlined, TagOutlined, CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listCustomers, toggleBlacklist, softDeleteCustomer, setCustomerTags, updateCustomer, isChurnRisk } from '@/services/customerService';
import { listAfterSales } from '@/services/afterSalesService';
import { listTransactions } from '@/services/transactionService';
import { getReferrerRankings } from '@/services/referralService';
import { exportCustomersCSV, downloadFile } from '@/utils/export';
import { formatMoney } from '@/utils/format';
import { formatDate } from '@/utils/date';
import dayjs from 'dayjs';
import type { Customer, CustomerLevel } from '@/types';

const levelMap: Record<CustomerLevel, { label: string; color: string }> = {
  normal: { label: '普通', color: 'default' },
  vip: { label: 'VIP', color: 'gold' },
  core: { label: '核心', color: 'red' },
};

export default function CustomerList() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Customer[]>([]);
  const [keyword, setKeyword] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [tagFilter, setTagFilter] = useState<string>('');
  const [hasAftersalesIds, setHasAftersalesIds] = useState<Set<number>>(new Set());
  const [referrerIds, setReferrerIds] = useState<Set<number>>(new Set());
  const [lastTradeMap, setLastTradeMap] = useState<Map<number, Date>>(new Map());
  const [editOpen, setEditOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [editForm] = Form.useForm();
  const [tagOpen, setTagOpen] = useState(false);
  const [tagCustomerId, setTagCustomerId] = useState<number | null>(null);
  const [tagValues, setTagValues] = useState<string[]>([]);
  const [loadError, setLoadError] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [list, aftersales, rankings, trades] = await Promise.all([
        listCustomers(),
        listAfterSales(),
        getReferrerRankings(),
        listTransactions(),
      ]);
      list.sort((a, b) => (b.first_trade_at ? new Date(b.first_trade_at).getTime() : 0) - (a.first_trade_at ? new Date(a.first_trade_at).getTime() : 0));
      setData(list);
      // 计算每个客户最近交易时间
      const lastMap = new Map<number, Date>();
      trades.forEach((t) => {
        if (t.deleted_at) return;
        const cur = lastMap.get(t.customer_id);
        const d = new Date(t.trade_at);
        if (!cur || d.getTime() > cur.getTime()) {
          lastMap.set(t.customer_id, d);
        }
      });
      setLastTradeMap(lastMap);
      // 通过售后工单关联的交易，反查客户 ID
      const transactionById = new Map(
        trades
          .filter((trade) => trade.id !== undefined)
          .map((trade) => [trade.id!, trade]),
      );
      const asCustomerIds = new Set<number>();
      aftersales.forEach((ticket) => {
        const transaction = transactionById.get(ticket.transaction_id);
        if (transaction) asCustomerIds.add(transaction.customer_id);
      });
      setHasAftersalesIds(asCustomerIds);
      // 介绍人 ID 集合
      setReferrerIds(new Set(rankings.map((ranking) => ranking.referrerId)));
    } catch (err) {
      console.error('客户数据加载失败:', err);
      setLoadError(true);
      message.error('数据加载失败，请重试');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filtered = useMemo(() => data.filter((c) => {
    if (keyword) {
      const lower = keyword.toLowerCase();
      if (!c.xianyu_nickname.toLowerCase().includes(lower) && !(c.contact_info || '').toLowerCase().includes(lower)) return false;
    }
    if (tagFilter && !c.tags.includes(tagFilter)) return false;
    if (activeTab === 'vip') return c.level === 'vip';
    if (activeTab === 'core') return c.level === 'core';
    if (activeTab === 'blacklist') return c.is_blacklist;
    if (activeTab === 'aftersales') return hasAftersalesIds.has(c.id!);
    if (activeTab === 'referrer') return referrerIds.has(c.id!);
    if (activeTab === 'churn') {
      return isChurnRisk(lastTradeMap.get(c.id!));
    }
    return true;
  }), [data, keyword, tagFilter, activeTab, hasAftersalesIds, referrerIds, lastTradeMap]);

  const churnCount = useMemo(() => data.filter((c) => isChurnRisk(lastTradeMap.get(c.id!))).length, [data, lastTradeMap]);

  const allTags = useMemo(() => Array.from(new Set(data.flatMap((c) => c.tags))).sort(), [data]);

  const handleToggleBlacklist = async (id: number) => {
    try {
      await toggleBlacklist(id);
      message.success('已更新');
      loadData();
    } catch (err) {
      console.error('黑名单切换失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await softDeleteCustomer(id);
      message.success('客户已删除');
      loadData();
    } catch (err) {
      console.error('删除客户失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleExport = () => {
    const csv = exportCustomersCSV(filtered);
    downloadFile(csv, `客户明细_${dayjs().format('YYYYMMDD_HHmmss')}.csv`, 'text/csv');
    message.success(`已导出 ${filtered.length} 条客户记录`);
  };

  const handleEdit = (c: Customer) => {
    setEditingCustomer(c);
    editForm.setFieldsValue({
      xianyu_nickname: c.xianyu_nickname,
      contact_info: c.contact_info || '',
      notes: c.notes || '',
    });
    setEditOpen(true);
  };

  const handleSaveEdit = async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingCustomer) return;
      await updateCustomer(editingCustomer.id!, {
        xianyu_nickname: values.xianyu_nickname.trim(),
        contact_info: values.contact_info,
        notes: values.notes,
      });
      message.success('客户信息已更新');
      setEditOpen(false);
      setEditingCustomer(null);
      editForm.resetFields();
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return; // 表单校验错误，不提示
      console.error('保存客户失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleManageTags = (c: Customer) => {
    setTagCustomerId(c.id!);
    setTagValues(c.tags);
    setTagOpen(true);
  };

  const handleSaveTags = async () => {
    if (tagCustomerId === null) return;
    try {
      await setCustomerTags(tagCustomerId, tagValues);
      message.success('标签已更新');
      setTagOpen(false);
      setTagCustomerId(null);
      loadData();
    } catch (err) {
      console.error('保存标签失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleContact = async (c: Customer) => {
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
      title: '客户',
      dataIndex: 'xianyu_nickname',
      render: (name: string, r: Customer) => (
        <Space>
          <Avatar style={{ background: r.level === 'core' ? 'var(--color-danger)' : r.level === 'vip' ? 'var(--color-warning)' : 'var(--color-info)' }}>
            {name.charAt(0)}
          </Avatar>
          <a onClick={() => navigate(`/customers/${r.id}`)}>{name}</a>
        </Space>
      ),
    },
    {
      title: '等级',
      dataIndex: 'level',
      width: 80,
      render: (l: CustomerLevel) => <Tag color={levelMap[l].color}>{levelMap[l].label}</Tag>,
    },
    {
      title: '累计消费',
      dataIndex: 'total_spent',
      width: 120,
      sorter: (a: Customer, b: Customer) => a.total_spent - b.total_spent,
      render: (v: number) => <span className="tabular-nums" style={{ fontWeight: 500 }}>{formatMoney(v)}</span>,
      align: 'right' as const,
    },
    {
      title: '交易笔数',
      dataIndex: 'trade_count',
      width: 100,
      sorter: (a: Customer, b: Customer) => a.trade_count - b.trade_count,
      align: 'center' as const,
    },
    {
      title: '首次交易',
      dataIndex: 'first_trade_at',
      width: 120,
      render: (v?: Date) => (v ? formatDate(v) : '-'),
    },
    {
      title: '最近交易',
      width: 120,
      sorter: (a: Customer, b: Customer) => {
        const la = lastTradeMap.get(a.id!)?.getTime() || 0;
        const lb = lastTradeMap.get(b.id!)?.getTime() || 0;
        return la - lb;
      },
      render: (_: unknown, r: Customer) => {
        const d = lastTradeMap.get(r.id!);
        if (!d) return <span style={{ color: 'var(--color-text-tertiary)' }}>-</span>;
        const days = Math.floor((Date.now() - d.getTime()) / (24 * 60 * 60 * 1000));
        const isStale = days > 30;
        return (
          <Tooltip title={isStale ? `已 ${days} 天未交易，建议回访` : undefined}>
            <span style={{ color: isStale ? 'var(--theme-primary)' : 'inherit' }}>{formatDate(d)}</span>
          </Tooltip>
        );
      },
    },
    {
      title: '标签',
      dataIndex: 'tags',
      render: (tags: string[]) => tags.length > 0 ? tags.map((t) => <Tag key={t}>{t}</Tag>) : <span style={{ color: 'var(--color-text-tertiary)' }}>-</span>,
    },
    {
      title: '联系方式',
      dataIndex: 'contact_info',
      width: 140,
      render: (v?: string) => v || <span style={{ color: 'var(--color-text-tertiary)' }}>-</span>,
    },
    {
      title: '操作',
      width: 260,
      render: (_: unknown, r: Customer) => (
        <Space size={0}>
          <Tooltip title="详情"><Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/customers/${r.id}`)} /></Tooltip>
          <Tooltip title="编辑"><Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(r)} /></Tooltip>
          <Tooltip title="添加标签"><Button type="link" size="small" icon={<TagOutlined />} onClick={() => handleManageTags(r)} /></Tooltip>
          <Tooltip title="复制联系方式"><Button type="link" size="small" icon={<CopyOutlined />} onClick={() => handleContact(r)} /></Tooltip>
          <Tooltip title={r.is_blacklist ? '取消黑名单' : '加入黑名单'}>
            <Popconfirm title={r.is_blacklist ? '取消黑名单？' : '加入黑名单？'} onConfirm={() => handleToggleBlacklist(r.id!)}>
              <Button type="link" size="small" danger={!r.is_blacklist} icon={r.is_blacklist ? <CheckCircleOutlined /> : <StopOutlined />} />
            </Popconfirm>
          </Tooltip>
          <Tooltip title="删除客户">
            <Popconfirm title="确认删除该客户？" description="删除后客户将不再显示，关联交易数据保留。" onConfirm={() => handleDelete(r.id!)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="客户管理"
      extra={
        <Space>
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/transactions/new')}>新增交易（含新客户）</Button>
        </Space>
      }
    >
      {loadError ? (
        <Result
          status="error"
          title="加载失败"
          subTitle="无法加载客户数据，可能是浏览器存储异常或被占用"
          extra={[
            <Button key="retry" type="primary" icon={<ReloadOutlined />} onClick={() => loadData()}>重试</Button>,
          ]}
        />
      ) : (
        <>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'all', label: '全部' },
          { key: 'vip', label: 'VIP' },
          { key: 'core', label: '核心' },
          { key: 'blacklist', label: '黑名单' },
          { key: 'aftersales', label: '有售后' },
          { key: 'referrer', label: '有介绍人' },
          { key: 'churn', label: <span style={{ color: churnCount > 0 ? 'var(--theme-primary)' : undefined }}>流失风险 ({churnCount})</span> },
        ]}
      />
      <Space style={{ marginBottom: 16 }}>
        <Input.Search placeholder="搜索昵称或联系方式" allowClear style={{ width: 300 }} value={keyword} onChange={(e) => setKeyword(e.target.value)} />
        <Select
          style={{ width: 150 }}
          placeholder="标签筛选"
          allowClear
          value={tagFilter || undefined}
          onChange={(v) => setTagFilter(v || '')}
          options={allTags.map((t) => ({ value: t, label: t }))}
        />
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={filtered}
        columns={columns}
        size="middle"
        locale={{
          emptyText: data.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  暂无客户
                  <Button type="link" size="small" icon={<PlusOutlined />} onClick={() => navigate('/transactions/new')}>
                    添加首位客户
                  </Button>
                </span>
              }
            />
          ) : (
            <Empty description="未匹配到符合条件的客户" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ),
        }}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 位客户` }}
      />
        </>
      )}

      <Modal
        title="编辑客户"
        open={editOpen}
        onCancel={() => { setEditOpen(false); setEditingCustomer(null); editForm.resetFields(); }}
        onOk={handleSaveEdit}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="xianyu_nickname" label="闲鱼昵称" rules={[{ required: true, message: '请输入昵称' }]}>
            <Input placeholder="闲鱼昵称" />
          </Form.Item>
          <Form.Item name="contact_info" label="联系方式">
            <Input placeholder="微信/手机号/邮箱" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={4} placeholder="客户备注" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="管理标签"
        open={tagOpen}
        onCancel={() => { setTagOpen(false); setTagCustomerId(null); }}
        onOk={handleSaveTags}
        okText="保存"
        cancelText="取消"
      >
        <Select
          mode="tags"
          style={{ width: '100%' }}
          placeholder="输入或选择标签（回车添加）"
          value={tagValues}
          onChange={(values) => setTagValues(values as string[])}
          options={allTags.map((t) => ({ value: t, label: t }))}
          tokenSeparators={[',']}
        />
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-secondary)' }}>
          可选择已有标签或输入新标签，按回车添加
        </div>
      </Modal>
    </Card>
  );
}
