import { useEffect, useState } from 'react';
import { Card, Form, Input, InputNumber, Radio, DatePicker, Button, Space, Row, Col, Divider, message, Modal, Switch, Tag } from 'antd';
import { ArrowLeftOutlined, SaveOutlined, PlusCircleOutlined } from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import CustomerSelect from '@/components/CustomerSelect';
import ProductTemplateSelect from '@/components/ProductTemplateSelect';
import AttachmentUpload from '@/components/AttachmentUpload';
import { createCustomer, findByNickname, getCustomer } from '@/services/customerService';
import { createTransaction, updateTransaction, getTransaction, calcProfit } from '@/services/transactionService';
import { useAppStore } from '@/store/useAppStore';
import { formatMoney } from '@/utils/format';
import { calcWarrantyEnd, getEnabledWarrantyDays, getWarrantyFormDefaults } from '@/utils/warranty';
import type { Customer, SourceType, TransactionStatus, TransactionInput } from '@/types';

const { TextArea } = Input;

export default function TransactionForm() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const presetCustomerId = searchParams.get('customerId');
  const isEdit = !!id;
  const { settings, refreshAll } = useAppStore();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [customer, setCustomer] = useState<Customer | undefined>();
  const [isNewCustomer, setIsNewCustomer] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [salePrice, setSalePrice] = useState(0);
  const [costPrice, setCostPrice] = useState(0);
  const initialWarranty = getWarrantyFormDefaults(settings.warranty_days);
  const [warrantyDays, setWarrantyDays] = useState(initialWarranty.warrantyDays);
  const [hasWarranty, setHasWarranty] = useState(initialWarranty.hasWarranty);
  const [sourceType, setSourceType] = useState<SourceType>('direct');
  const [tradeAt, setTradeAt] = useState<dayjs.Dayjs>(dayjs());
  const [shippedAt, setShippedAt] = useState<dayjs.Dayjs>(dayjs());
  const [status, setStatus] = useState<TransactionStatus>('completed');

  useEffect(() => {
    if (isEdit) {
      loadEditData();
    } else if (presetCustomerId) {
      // 从 URL 参数预选客户
      loadPresetCustomer(Number(presetCustomerId));
    }
  }, [id]);

  const loadPresetCustomer = async (cid: number) => {
    const c = await getCustomer(cid);
    if (c) {
      setCustomer(c);
      form.setFieldValue('customer_id', cid);
    }
  };

  const loadEditData = async () => {
    const t = await getTransaction(Number(id));
    if (!t) {
      message.error('交易不存在');
      navigate('/transactions');
      return;
    }
    const c = await getCustomer(t.customer_id);
    setCustomer(c);
    setSalePrice(t.sale_price);
    setCostPrice(t.cost_price);
    setWarrantyDays(t.warranty_days);
    setHasWarranty(t.warranty_days > 0);
    setSourceType(t.source_type);
    setTradeAt(dayjs(t.trade_at));
    setShippedAt(t.shipped_at ? dayjs(t.shipped_at) : dayjs(t.trade_at));
    setStatus(t.status);
    form.setFieldsValue({
      customer_id: t.customer_id,
      xianyu_order_no: t.xianyu_order_no,
      product_name: t.product_name,
      product_template_id: t.product_template_id,
      sale_price: t.sale_price,
      cost_price: t.cost_price,
      warranty_days: t.warranty_days,
      has_warranty: t.warranty_days > 0,
      source_type: t.source_type,
      source_customer_id: t.source_customer_id,
      notes: t.notes,
      status: t.status,
      trade_at: dayjs(t.trade_at),
      shipped_at: t.shipped_at ? dayjs(t.shipped_at) : dayjs(t.trade_at),
      attachments: t.attachments || [],
    });
  };

  const profit = calcProfit(salePrice, costPrice);
  const warrantyStart = shippedAt || tradeAt;
  const warrantyEnd = status === 'completed' && hasWarranty && warrantyDays > 0
    ? calcWarrantyEnd(warrantyStart.toDate(), warrantyDays)
    : undefined;
  const expectedRebate = sourceType === 'introduced' ? Math.round((settings.rebate_base === 'sale' ? salePrice : profit) * settings.rebate_rate * 100) / 100 : 0;

  // 黑名单警示
  useEffect(() => {
    if (customer?.is_blacklist) {
      Modal.warning({
        title: '黑名单客户警示',
        content: `客户「${customer.xianyu_nickname}」已被标记为黑名单，请谨慎交易！`,
        okText: '知道了',
      });
    }
  }, [customer]);

  const handleTemplateChange = (_: unknown, tpl?: { default_cost: number; default_sale_price?: number; name: string; warranty_days: number }) => {
    if (tpl) {
      setCostPrice(tpl.default_cost);
      if (tpl.default_sale_price) setSalePrice(tpl.default_sale_price);
      setWarrantyDays(tpl.warranty_days);
      setHasWarranty(tpl.warranty_days > 0);
      form.setFieldsValue({
        product_name: tpl.name,
        cost_price: tpl.default_cost,
        sale_price: tpl.default_sale_price,
        warranty_days: tpl.warranty_days,
        has_warranty: tpl.warranty_days > 0,
      });
    }
  };

  const handleWarrantyToggle = (checked: boolean) => {
    setHasWarranty(checked);
    if (checked) {
      const nextDays = getEnabledWarrantyDays(warrantyDays, settings.warranty_days);
      setWarrantyDays(nextDays);
      form.setFieldValue('warranty_days', nextDays);
    } else {
      setWarrantyDays(0);
      form.setFieldValue('warranty_days', 0);
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      let customerId = values.customer_id;

      // 新客户创建
      if (isNewCustomer) {
        if (!newNickname.trim()) {
          message.error('请输入客户昵称');
          setLoading(false);
          return;
        }
        const existing = await findByNickname(newNickname);
        if (existing) {
          customerId = existing.id;
          message.info(`客户「${existing.xianyu_nickname}」已存在，已自动关联`);
        } else {
          const c = await createCustomer({ xianyu_nickname: newNickname, contact_info: values.contact_info });
          customerId = c.id;
        }
      }

      if (!customerId) {
        message.error('请选择客户');
        setLoading(false);
        return;
      }

      // 介绍来源校验
      if (values.source_type === 'introduced' && !values.source_customer_id) {
        message.error('请选择介绍人');
        setLoading(false);
        return;
      }
      if (values.source_type === 'introduced' && values.source_customer_id === customerId) {
        message.error('介绍人不能是买家本人');
        setLoading(false);
        return;
      }

      const input: TransactionInput = {
        customer_id: customerId,
        xianyu_order_no: values.xianyu_order_no,
        product_name: values.product_name,
        product_template_id: values.product_template_id,
        sale_price: Number(values.sale_price),
        cost_price: Number(values.cost_price),
        trade_at: (values.trade_at || tradeAt).toDate(),
        shipped_at: (values.status || status) === 'completed'
          ? (values.shipped_at || shippedAt || values.trade_at || tradeAt).toDate()
          : undefined,
        status: values.status || status,
        warranty_days: values.has_warranty === false ? 0 : Number(values.warranty_days ?? warrantyDays),
        source_type: values.source_type || sourceType,
        source_customer_id: values.source_customer_id,
        notes: values.notes,
        attachments: values.attachments || [],
      };

      if (isEdit) {
        await updateTransaction(Number(id), input);
        message.success('交易已更新');
        refreshAll();
        navigate('/transactions');
      } else {
        await createTransaction(input);
        message.success('交易已创建');
        refreshAll();
        navigate('/transactions');
      }
    } catch (err: any) {
      if (err?.errorFields) return; // 表单校验错误
      message.error(err?.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  // 保存并继续：创建交易后重置表单，保留客户选择
  const handleSaveAndContinue = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      let customerId = values.customer_id;

      if (isNewCustomer) {
        if (!newNickname.trim()) {
          message.error('请输入客户昵称');
          setLoading(false);
          return;
        }
        const existing = await findByNickname(newNickname);
        if (existing) {
          customerId = existing.id;
        } else {
          const c = await createCustomer({ xianyu_nickname: newNickname, contact_info: values.contact_info });
          customerId = c.id;
        }
      }

      if (!customerId) {
        message.error('请选择客户');
        setLoading(false);
        return;
      }

      if (values.source_type === 'introduced' && !values.source_customer_id) {
        message.error('请选择介绍人');
        setLoading(false);
        return;
      }

      const input: TransactionInput = {
        customer_id: customerId,
        xianyu_order_no: values.xianyu_order_no,
        product_name: values.product_name,
        product_template_id: values.product_template_id,
        sale_price: Number(values.sale_price),
        cost_price: Number(values.cost_price),
        trade_at: (values.trade_at || tradeAt).toDate(),
        shipped_at: (values.status || status) === 'completed'
          ? (values.shipped_at || shippedAt || values.trade_at || tradeAt).toDate()
          : undefined,
        status: values.status || status,
        warranty_days: values.has_warranty === false ? 0 : Number(values.warranty_days ?? warrantyDays),
        source_type: values.source_type || sourceType,
        source_customer_id: values.source_customer_id,
        notes: values.notes,
        attachments: values.attachments || [],
      };

      await createTransaction(input);
      message.success('交易已创建，可继续录入下一笔');
      refreshAll();

      // 重置表单但保留客户选择和来源
      form.resetFields(['product_name', 'xianyu_order_no', 'sale_price', 'cost_price', 'notes', 'product_template_id', 'attachments']);
      form.setFieldsValue({
        customer_id: customerId,
        source_type: values.source_type,
        source_customer_id: values.source_customer_id,
        status: 'completed',
        trade_at: dayjs(),
        shipped_at: dayjs(),
        has_warranty: initialWarranty.hasWarranty,
        warranty_days: initialWarranty.warrantyDays,
      });
      setSalePrice(0);
      setCostPrice(0);
      setWarrantyDays(initialWarranty.warrantyDays);
      setHasWarranty(initialWarranty.hasWarranty);
      setTradeAt(dayjs());
      setShippedAt(dayjs());
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title={
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} />
          <span>{isEdit ? '编辑交易' : '新增交易'}</span>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>取消</Button>
          {!isEdit && (
            <Button icon={<PlusCircleOutlined />} loading={loading} onClick={handleSaveAndContinue}>
              保存并继续
            </Button>
          )}
          <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={handleSubmit}>保存</Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" initialValues={{ status: 'completed', source_type: 'direct', has_warranty: initialWarranty.hasWarranty, warranty_days: initialWarranty.warrantyDays, trade_at: dayjs(), shipped_at: dayjs() }}>
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            <Card type="inner" title="客户信息" size="small">
              <Form.Item label="客户选择方式">
                <Radio.Group value={isNewCustomer} onChange={(e) => setIsNewCustomer(e.target.value)}>
                  <Radio.Button value={false}>选择老客户</Radio.Button>
                  <Radio.Button value={true}>新建客户</Radio.Button>
                </Radio.Group>
              </Form.Item>

              {isNewCustomer ? (
                <>
                  <Form.Item label="闲鱼昵称" required>
                    <Input placeholder="输入新客户闲鱼昵称" value={newNickname} onChange={(e) => setNewNickname(e.target.value)} />
                  </Form.Item>
                  <Form.Item name="contact_info" label="联系方式（选填）">
                    <Input placeholder="微信/手机号" />
                  </Form.Item>
                </>
              ) : (
                <>
                  <Form.Item name="customer_id" label="闲鱼昵称" rules={[{ required: true, message: '请选择客户' }]}>
                    <CustomerSelect value={undefined} onChange={(_v, c) => setCustomer(c)} />
                  </Form.Item>
                  {customer && (
                    <div style={{ marginBottom: 16, fontSize: 12, color: 'var(--color-text-secondary)' }}>
                      累计消费 {formatMoney(customer.total_spent)} · {customer.trade_count} 笔 · 等级{' '}
                      <Tag color={customer.level === 'core' ? 'red' : customer.level === 'vip' ? 'gold' : 'default'}>
                        {customer.level === 'core' ? '核心' : customer.level === 'vip' ? 'VIP' : '普通'}
                      </Tag>
                      {customer.is_blacklist && <Tag color="red">黑名单</Tag>}
                    </div>
                  )}
                </>
              )}
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card type="inner" title="交易信息" size="small">
              <Form.Item name="product_template_id" label="商品模板（选填，自动填充）">
                <ProductTemplateSelect value={undefined} onChange={handleTemplateChange} />
              </Form.Item>
              <Form.Item name="product_name" label="商品名称" rules={[{ required: true, message: '请输入商品名称' }]}>
                <Input placeholder="商品名称" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="sale_price" label="售价" rules={[{ required: true, message: '请输入售价' }]}>
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      precision={2}
                      prefix="¥"
                      value={salePrice}
                      onChange={(v) => setSalePrice(Number(v) || 0)}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="cost_price" label="成本" rules={[{ required: true, message: '请输入成本' }]}>
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      precision={2}
                      prefix="¥"
                      value={costPrice}
                      onChange={(v) => setCostPrice(Number(v) || 0)}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--color-success-light)', borderRadius: 6 }}>
                利润：<span style={{ color: 'var(--color-success)', fontWeight: 600, fontSize: 16 }} className="tabular-nums">{formatMoney(profit)}</span>
              </div>
              <Form.Item name="xianyu_order_no" label="闲鱼订单号（选填）">
                <Input placeholder="闲鱼订单号" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="trade_at" label="交易时间">
                    <DatePicker showTime style={{ width: '100%' }} value={tradeAt} onChange={(v) => v && setTradeAt(v)} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="status" label="交易状态">
                    <Radio.Group value={status} onChange={(e) => setStatus(e.target.value)}>
                      <Radio.Button value="pending">待发货</Radio.Button>
                      <Radio.Button value="completed">已完成</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="shipped_at" label="发货时间（质保起算）" tooltip="质保从你发货的时间开始计算；待发货订单暂不生成质保到期时间。">
                <DatePicker
                  showTime
                  style={{ width: '100%' }}
                  disabled={status !== 'completed'}
                  value={shippedAt}
                  onChange={(v) => v && setShippedAt(v)}
                />
              </Form.Item>
            </Card>
          </Col>
        </Row>

        <Row gutter={24} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <Card type="inner" title="来源与质保" size="small">
              <Form.Item name="source_type" label="客户来源">
                <Radio.Group value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                  <Radio.Button value="direct">直接下单</Radio.Button>
                  <Radio.Button value="introduced">客户介绍</Radio.Button>
                  <Radio.Button value="repeat">老客复购</Radio.Button>
                </Radio.Group>
              </Form.Item>

              {sourceType === 'introduced' && (
                <Form.Item name="source_customer_id" label="介绍人" rules={[{ required: true, message: '请选择介绍人' }]}>
                  <CustomerSelect placeholder="搜索介绍人昵称" excludeId={customer?.id} />
                </Form.Item>
              )}

              <Form.Item name="has_warranty" label="订单质保" valuePropName="checked">
                <Switch checked={hasWarranty} onChange={handleWarrantyToggle} checkedChildren="质保" unCheckedChildren="不质保" />
              </Form.Item>

              {hasWarranty ? (
                <Form.Item name="warranty_days" label="质保周期（天）">
                  <InputNumber min={1} max={3650} value={warrantyDays} onChange={(v) => setWarrantyDays(Number(v) || 0)} style={{ width: 120 }} />
                </Form.Item>
              ) : (
                <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--color-bg)', borderRadius: 6, fontSize: 13, color: 'var(--color-text-secondary)' }}>
                  此订单不进入质保看板，也不会生成到期提醒。
                </div>
              )}

              {warrantyEnd && (
                <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--color-text-secondary)' }}>
                  质保到期：<span style={{ color: 'var(--color-dark)' }}>{dayjs(warrantyEnd).format('YYYY-MM-DD HH:mm')}</span>
                  <span style={{ marginLeft: 8 }}>从 {shippedAt.format('YYYY-MM-DD HH:mm')} 发货开始</span>
                </div>
              )}

              {expectedRebate > 0 && (
                <div style={{ padding: '8px 12px', background: 'var(--theme-primary-light)', borderRadius: 6, fontSize: 13 }}>
                  预计返利：<span style={{ color: 'var(--theme-primary)', fontWeight: 600 }} className="tabular-nums">{formatMoney(expectedRebate)}</span>
                  <span style={{ color: 'var(--color-text-secondary)', marginLeft: 8 }}>（{settings.rebate_base === 'profit' ? '利润' : '售价'} × {Math.round(settings.rebate_rate * 100)}%）</span>
                </div>
              )}
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card type="inner" title="备注与附件" size="small">
              <Form.Item name="notes" label="交易备注">
                <TextArea rows={4} placeholder="添加交易备注..." />
              </Form.Item>
              <Form.Item name="attachments" label="交易附件">
                <AttachmentUpload />
              </Form.Item>
            </Card>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}
