import { useEffect, useState } from 'react';
import { Card, Form, Button, Space, Row, Col, message, Modal } from 'antd';
import { ArrowLeftOutlined, SaveOutlined, PlusCircleOutlined } from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import dayjs from 'dayjs';
import { getCustomer } from '@/services/customerService';
import { createTransaction, updateTransaction, getTransaction, calcProfit } from '@/services/transactionService';
import { useAppStore } from '@/store/useAppStore';
import { calcWarrantyEnd, getEnabledWarrantyDays, getWarrantyFormDefaults } from '@/utils/warranty';
import { getErrorMessage, isValidationError } from '@/utils/error';
import type { Customer, SourceType, ChannelType, TransactionStatus } from '@/types';
import CustomerInfoCard from './form/CustomerInfoCard';
import TransactionInfoCard from './form/TransactionInfoCard';
import SourceWarrantyCard from './form/SourceWarrantyCard';
import NotesAttachmentsCard from './form/NotesAttachmentsCard';
import { buildTransactionInput, resolveCustomerId } from './form/buildTransactionInput';
import { useUnsavedChanges } from '@/hooks/useUnsavedChanges';

export default function TransactionForm() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const presetCustomerId = searchParams.get('customerId');
  const isEdit = !!id;
  const { settings, refreshAll } = useAppStore();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [customer, setCustomer] = useState<Customer | undefined>();
  const [isNewCustomer, setIsNewCustomer] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [salePrice, setSalePrice] = useState(0);
  const [costPrice, setCostPrice] = useState(0);
  const initialWarranty = getWarrantyFormDefaults(settings.warranty_days);
  const [warrantyDays, setWarrantyDays] = useState(initialWarranty.warrantyDays);
  const [hasWarranty, setHasWarranty] = useState(initialWarranty.hasWarranty);
  const [sourceType, setSourceType] = useState<SourceType>('direct');
  const [channel, setChannel] = useState<ChannelType>('xianyu');
  const [tradeAt, setTradeAt] = useState<dayjs.Dayjs>(dayjs());
  const [shippedAt, setShippedAt] = useState<dayjs.Dayjs>(dayjs());
  const [status, setStatus] = useState<TransactionStatus>('completed');
  const { allowNavigation } = useUnsavedChanges({ dirty, submitting: loading });

  useEffect(() => {
    if (isEdit) {
      loadEditData();
    } else if (presetCustomerId) {
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
    setChannel(t.channel);
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
      channel: t.channel,
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
      setDirty(true);
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

      const { customerId, message: msg, messageText } = await resolveCustomerId(values, isNewCustomer, newNickname, values.customer_id);
      if (msg === 'info' && messageText) message.info(messageText);
      if (!customerId) {
        if (messageText) message.error(messageText);
        setLoading(false);
        return;
      }

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

      const input = buildTransactionInput({
        form,
        customerId,
        fallbackTradeAt: tradeAt,
        fallbackShippedAt: shippedAt,
        fallbackStatus: status,
        fallbackSourceType: sourceType,
        fallbackChannel: channel,
        fallbackWarrantyDays: warrantyDays,
      });

      if (isEdit) {
        await updateTransaction(Number(id), input);
        message.success('交易已更新');
      } else {
        await createTransaction(input);
        message.success('交易已创建');
      }
      refreshAll();
      allowNavigation();
      setDirty(false);
      navigate('/transactions');
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      message.error(getErrorMessage(err, '操作失败'));
    } finally {
      setLoading(false);
    }
  };

  // 保存并继续：创建交易后重置表单，保留客户选择
  const handleSaveAndContinue = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const { customerId, message: msg, messageText } = await resolveCustomerId(values, isNewCustomer, newNickname, values.customer_id);
      if (msg === 'info' && messageText) message.info(messageText);
      if (!customerId) {
        if (messageText) message.error(messageText);
        setLoading(false);
        return;
      }

      if (values.source_type === 'introduced' && !values.source_customer_id) {
        message.error('请选择介绍人');
        setLoading(false);
        return;
      }

      const input = buildTransactionInput({
        form,
        customerId,
        fallbackTradeAt: tradeAt,
        fallbackShippedAt: shippedAt,
        fallbackStatus: status,
        fallbackSourceType: sourceType,
        fallbackChannel: channel,
        fallbackWarrantyDays: warrantyDays,
      });

      await createTransaction(input);
      message.success('交易已创建，可继续录入下一笔');
      refreshAll();

      // 重置表单但保留客户选择和来源
      form.resetFields(['product_name', 'xianyu_order_no', 'sale_price', 'cost_price', 'notes', 'product_template_id', 'attachments']);
      form.setFieldsValue({
        customer_id: customerId,
        source_type: values.source_type,
        channel: values.channel,
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
      setDirty(false);
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      message.error(getErrorMessage(err, '操作失败'));
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
      <Form
        form={form}
        layout="vertical"
        onValuesChange={() => setDirty(true)}
        initialValues={{ status: 'completed', source_type: 'direct', channel: 'xianyu', has_warranty: initialWarranty.hasWarranty, warranty_days: initialWarranty.warrantyDays, trade_at: dayjs(), shipped_at: dayjs() }}
      >
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            <CustomerInfoCard
              form={form}
              isNewCustomer={isNewCustomer}
              onToggleNewCustomer={setIsNewCustomer}
              newNickname={newNickname}
              onNewNicknameChange={(value) => {
                setNewNickname(value);
                setDirty(true);
              }}
              customer={customer}
              onCustomerChange={setCustomer}
            />
          </Col>
          <Col xs={24} lg={12}>
            <TransactionInfoCard
              form={form}
              onTemplateChange={handleTemplateChange}
              salePrice={salePrice}
              onSalePriceChange={setSalePrice}
              costPrice={costPrice}
              onCostPriceChange={setCostPrice}
              profit={profit}
              channel={channel}
              onChannelChange={setChannel}
              status={status}
              onStatusChange={setStatus}
              tradeAt={tradeAt}
              onTradeAtChange={setTradeAt}
              shippedAt={shippedAt}
              onShippedAtChange={setShippedAt}
            />
          </Col>
        </Row>

        <Row gutter={24} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <SourceWarrantyCard
              form={form}
              sourceType={sourceType}
              onSourceTypeChange={setSourceType}
              customer={customer}
              hasWarranty={hasWarranty}
              onWarrantyToggle={handleWarrantyToggle}
              warrantyDays={warrantyDays}
              onWarrantyDaysChange={setWarrantyDays}
              warrantyEnd={warrantyEnd}
              shippedAt={shippedAt}
              expectedRebate={expectedRebate}
              rebateBase={settings.rebate_base}
              rebateRate={settings.rebate_rate}
            />
          </Col>
          <Col xs={24} lg={12}>
            <NotesAttachmentsCard form={form} />
          </Col>
        </Row>
      </Form>
    </Card>
  );
}
