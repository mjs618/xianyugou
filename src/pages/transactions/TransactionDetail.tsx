import { useEffect, useState } from 'react';
import { Card, Descriptions, Tag, Button, Space, Spin, Empty, Divider, message, Popconfirm, InputNumber, Input, Form, Modal, Steps } from 'antd';
import { ArrowLeftOutlined, EditOutlined, ToolOutlined, ClockCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { getTransaction, changeStatus, softDeleteTransaction } from '@/services/transactionService';
import { getCustomer } from '@/services/customerService';
import { listByTransaction, createAfterSales } from '@/services/afterSalesService';
import { extendWarranty, endWarrantyEarly, getWarrantyExtensions } from '@/services/warrantyService';
import { getRebateByTransaction } from '@/services/rebateService';
import WarrantyTag from '@/components/WarrantyTag';
import AttachmentUpload from '@/components/AttachmentUpload';
import { formatMoney } from '@/utils/format';
import { formatDate, formatDateTime } from '@/utils/date';
import { canManageWarranty, getWarrantyStartLabel } from '@/utils/warranty';
import { useAppStore } from '@/store/useAppStore';
import type { Transaction, Customer, AfterSales, WarrantyExtension, RebateRecord, TransactionStatus } from '@/types';

const statusMap: Record<TransactionStatus, { label: string; color: string }> = {
  pending: { label: '待发货', color: 'blue' },
  completed: { label: '已完成', color: 'green' },
  aftersales: { label: '售后中', color: 'orange' },
  closed: { label: '已关闭', color: 'default' },
};

const statusOrder: TransactionStatus[] = ['pending', 'completed', 'aftersales', 'closed'];

const aftersalesStatusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'red' },
  processing: { label: '处理中', color: 'orange' },
  resolved: { label: '已解决', color: 'green' },
  closed: { label: '已关闭', color: 'default' },
};

export default function TransactionDetail() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { refreshAll } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [customer, setCustomer] = useState<Customer | undefined>();
  const [afterSales, setAfterSales] = useState<AfterSales[]>([]);
  const [extensions, setExtensions] = useState<WarrantyExtension[]>([]);
  const [rebate, setRebate] = useState<RebateRecord | undefined>();
  const [extendModalOpen, setExtendModalOpen] = useState(false);
  const [asModalOpen, setAsModalOpen] = useState(false);
  const [asIssueDesc, setAsIssueDesc] = useState('');
  const [asAttachments, setAsAttachments] = useState<string[]>([]);
  const [extendForm] = Form.useForm();
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const t = await getTransaction(Number(id));
      if (!t) {
        message.error('交易不存在');
        navigate('/transactions');
        return;
      }
      setTransaction(t);
      const [c, as, ext, rb] = await Promise.all([
        getCustomer(t.customer_id),
        listByTransaction(t.id!),
        getWarrantyExtensions(t.id!),
        getRebateByTransaction(t.id!),
      ]);
      setCustomer(c);
      setAfterSales(as);
      setExtensions(ext);
      setRebate(rb);
    } catch (err) {
      console.error('加载交易详情失败:', err);
      const msg = err instanceof Error ? err.message : '加载交易详情失败，请重试';
      setError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleStatusChange = async (status: TransactionStatus) => {
    try {
      await changeStatus(transaction!.id!, status);
      message.success('状态已更新');
      refreshAll();
      loadData();
    } catch (err) {
      console.error('更新交易状态失败:', err);
      message.error(err instanceof Error ? err.message : '状态更新失败，请重试');
    }
  };

  const handleDelete = async () => {
    try {
      await softDeleteTransaction(transaction!.id!);
      message.success('已删除');
      refreshAll();
      navigate('/transactions');
    } catch (err) {
      console.error('删除交易失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败，请重试');
    }
  };

  const handleCreateAfterSales = async () => {
    if (!asIssueDesc.trim()) {
      message.error('请填写问题描述');
      return;
    }
    try {
      await createAfterSales({ transaction_id: transaction!.id!, issue_desc: asIssueDesc.trim(), attachments: asAttachments });
      message.success('售后工单已创建');
      setAsModalOpen(false);
      setAsIssueDesc('');
      setAsAttachments([]);
      refreshAll();
      loadData();
    } catch (err) {
      console.error('创建售后工单失败:', err);
      message.error(err instanceof Error ? err.message : '创建售后工单失败，请重试');
    }
  };

  const handleExtend = async () => {
    try {
      const values = await extendForm.validateFields();
      await extendWarranty(transaction!.id!, Number(values.days), values.reason);
      message.success(`质保已延长 ${values.days} 天`);
      setExtendModalOpen(false);
      extendForm.resetFields();
      refreshAll();
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return; // 表单校验错误
      console.error('延长质保失败:', err);
      message.error(err instanceof Error ? err.message : '延长质保失败，请重试');
    }
  };

  const handleEndWarranty = async () => {
    try {
      await endWarrantyEarly(transaction!.id!);
      message.success('质保已提前结束');
      refreshAll();
      loadData();
    } catch (err) {
      console.error('提前结束质保失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败，请重试');
    }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  if (error) return (
    <Card>
      <Empty description={error}>
        <Button type="primary" onClick={loadData}>重试</Button>
      </Empty>
    </Card>
  );
  if (!transaction) return <Empty />;
  const canManageTransactionWarranty = canManageWarranty(transaction);

  return (
    <Card
      title={
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} />
          <span>交易详情</span>
          <Tag color={statusMap[transaction.status].color}>{statusMap[transaction.status].label}</Tag>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<EditOutlined />} onClick={() => navigate(`/transactions/${transaction.id}/edit`)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={handleDelete} okText="删除" cancelText="取消">
            <Button danger>删除</Button>
          </Popconfirm>
        </Space>
      }
    >
      <Descriptions title="基本信息" bordered column={{ xs: 1, sm: 2 }} size="small">
        <Descriptions.Item label="商品名称">{transaction.product_name}</Descriptions.Item>
        <Descriptions.Item label="闲鱼订单号">{transaction.xianyu_order_no || '-'}</Descriptions.Item>
        <Descriptions.Item label="售价">{formatMoney(transaction.sale_price)}</Descriptions.Item>
        <Descriptions.Item label="成本">{formatMoney(transaction.cost_price)}</Descriptions.Item>
        <Descriptions.Item label="利润">
          <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>{formatMoney(transaction.profit)}</span>
        </Descriptions.Item>
        <Descriptions.Item label="交易时间">{formatDateTime(transaction.trade_at)}</Descriptions.Item>
        <Descriptions.Item label="发货时间">{transaction.shipped_at ? formatDateTime(transaction.shipped_at) : '-'}</Descriptions.Item>
        <Descriptions.Item label="买家">
          {customer ? <a onClick={() => navigate(`/customers/${customer.id}`)}>{customer.xianyu_nickname}</a> : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="来源">
          {transaction.source_type === 'direct' ? '直接下单' : transaction.source_type === 'introduced' ? '客户介绍' : '老客复购'}
        </Descriptions.Item>
      </Descriptions>

      <Divider orientation="left">质保信息</Divider>
      <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
        <Descriptions.Item label="质保状态">
          <WarrantyTag warrantyEnd={transaction.warranty_end} status={transaction.status} />
        </Descriptions.Item>
        <Descriptions.Item label="质保周期">{transaction.warranty_days > 0 ? `${transaction.warranty_days} 天` : '不质保'}</Descriptions.Item>
        <Descriptions.Item label="起算时间">
          {getWarrantyStartLabel(transaction, formatDateTime)}
        </Descriptions.Item>
        <Descriptions.Item label="到期时间">
          {transaction.warranty_end ? formatDateTime(transaction.warranty_end) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="操作">
          {canManageTransactionWarranty ? (
            <Space>
              <Button size="small" icon={<ClockCircleOutlined />} onClick={() => setExtendModalOpen(true)}>延长质保</Button>
              <Popconfirm title="确认提前结束质保？" description="质保将立即失效，此操作不可撤销。" onConfirm={handleEndWarranty} okText="确认" cancelText="取消" okButtonProps={{ danger: true }}>
                <Button size="small" danger>提前结束</Button>
              </Popconfirm>
            </Space>
          ) : '-'}
        </Descriptions.Item>
      </Descriptions>

      {extensions.length > 0 && (
        <>
          <Divider orientation="left">质保延长历史</Divider>
          <Descriptions bordered column={1} size="small">
            {extensions.map((e) => (
              <Descriptions.Item key={e.id} label={`${formatDate(e.old_end)} → ${formatDate(e.new_end)}`}>
                延长 {e.extended_days} 天 {e.reason ? `· ${e.reason}` : ''} · {formatDate(e.created_at)}
              </Descriptions.Item>
            ))}
          </Descriptions>
        </>
      )}

      {rebate && (
        <>
          <Divider orientation="left">返利记录</Divider>
          <Descriptions bordered column={{ xs: 1, sm: 2 }} size="small">
            <Descriptions.Item label="返利金额">{formatMoney(rebate.amount)}</Descriptions.Item>
            <Descriptions.Item label="返利比例">{Math.round(rebate.rate * 100)}%</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={rebate.status === 'paid' ? 'green' : rebate.status === 'pending' ? 'orange' : 'default'}>
                {rebate.status === 'paid' ? '已支付' : rebate.status === 'pending' ? '待结算' : '已取消'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="支付时间">{rebate.paid_at ? formatDate(rebate.paid_at) : '-'}</Descriptions.Item>
          </Descriptions>
        </>
      )}

      <Divider orientation="left">售后工单</Divider>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAsModalOpen(true)}>创建售后工单</Button>
        <Button icon={<ToolOutlined />} onClick={() => navigate('/after-sales')}>售后管理</Button>
      </Space>
      {afterSales.length === 0 ? (
        <Empty description="暂无售后工单" />
      ) : (
        <Descriptions bordered column={1} size="small">
          {afterSales.map((a) => (
            <Descriptions.Item key={a.id} label={`工单 #${a.id}`}>
              {a.issue_desc} · <Tag color={aftersalesStatusMap[a.status]?.color || 'default'}>{aftersalesStatusMap[a.status]?.label || a.status}</Tag> · {formatDate(a.created_at)}
            </Descriptions.Item>
          ))}
        </Descriptions>
      )}

      {transaction.notes && (
        <>
          <Divider orientation="left">备注</Divider>
          <div style={{ padding: 12, background: 'var(--color-bg)', borderRadius: 6, whiteSpace: 'pre-wrap' }}>{transaction.notes}</div>
        </>
      )}

      <Divider orientation="left">交易附件</Divider>
      <AttachmentUpload value={transaction.attachments || []} disabled />

      <Divider orientation="left">状态流转</Divider>
      <Steps
        current={statusOrder.indexOf(transaction.status)}
        size="small"
        items={[
          { title: '待发货', description: transaction.status === 'pending' ? '当前状态' : undefined },
          { title: '已完成', description: transaction.status === 'completed' ? '当前状态' : undefined },
          { title: '售后中', description: transaction.status === 'aftersales' ? '当前状态' : undefined },
          { title: '已关闭', description: transaction.status === 'closed' ? '当前状态' : undefined },
        ]}
      />
      <Space style={{ marginTop: 16 }}>
        <Button disabled={transaction.status === 'pending'} onClick={() => handleStatusChange('pending')}>待发货</Button>
        <Button disabled={transaction.status === 'completed'} type="primary" onClick={() => handleStatusChange('completed')}>已完成</Button>
        <Button disabled={transaction.status === 'aftersales'} onClick={() => handleStatusChange('aftersales')}>售后中</Button>
        <Button disabled={transaction.status === 'closed'} onClick={() => handleStatusChange('closed')}>已关闭</Button>
      </Space>

      <Modal title="延长质保" open={extendModalOpen} onCancel={() => setExtendModalOpen(false)} onOk={handleExtend} okText="确认延长">
        <Form form={extendForm} layout="vertical">
          <Form.Item name="days" label="延长天数" rules={[{ required: true, message: '请输入天数' }]}>
            <InputNumber min={1} max={3650} style={{ width: '100%' }} placeholder="延长天数" />
          </Form.Item>
          <Form.Item name="reason" label="延长原因">
            <Input placeholder="选填" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="创建售后工单" open={asModalOpen} onCancel={() => { setAsModalOpen(false); setAsIssueDesc(''); setAsAttachments([]); }} onOk={handleCreateAfterSales} okText="创建">
        <div style={{ marginBottom: 4 }}>问题描述</div>
        <Input.TextArea rows={4} value={asIssueDesc} onChange={(e) => setAsIssueDesc(e.target.value)} placeholder="描述客户反馈的问题" />
        <div style={{ marginTop: 12, marginBottom: 4 }}>问题截图/附件</div>
        <AttachmentUpload value={asAttachments} onChange={setAsAttachments} maxCount={6} />
      </Modal>
    </Card>
  );
}
