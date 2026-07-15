import { Card, Form, Input, InputNumber, Radio, DatePicker, Row, Col } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import ProductTemplateSelect from '@/components/ProductTemplateSelect';
import { formatMoney } from '@/utils/format';
import type { ChannelType, TransactionStatus } from '@/types';

interface TransactionInfoCardProps {
  form: FormInstance;
  onTemplateChange: (val: unknown, tpl?: { default_cost: number; default_sale_price?: number; name: string; warranty_days: number }) => void;
  salePrice: number;
  onSalePriceChange: (v: number) => void;
  costPrice: number;
  onCostPriceChange: (v: number) => void;
  profit: number;
  channel: ChannelType;
  onChannelChange: (c: ChannelType) => void;
  status: TransactionStatus;
  onStatusChange: (s: TransactionStatus) => void;
  tradeAt: dayjs.Dayjs;
  onTradeAtChange: (v: dayjs.Dayjs) => void;
  shippedAt: dayjs.Dayjs;
  onShippedAtChange: (v: dayjs.Dayjs) => void;
}

/** 交易信息 Card：商品模板/名称/售价/成本/利润/渠道/订单号/交易时间/状态/发货时间。 */
export default function TransactionInfoCard({
  form,
  onTemplateChange,
  salePrice,
  onSalePriceChange,
  costPrice,
  onCostPriceChange,
  profit,
  channel,
  onChannelChange,
  status,
  onStatusChange,
  tradeAt,
  onTradeAtChange,
  shippedAt,
  onShippedAtChange,
}: TransactionInfoCardProps) {
  return (
    <Card type="inner" title="交易信息" size="small">
      <Form.Item name="product_template_id" label="商品模板（选填，自动填充）">
        <ProductTemplateSelect value={undefined} onChange={onTemplateChange} />
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
              onChange={(v) => onSalePriceChange(Number(v) || 0)}
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
              onChange={(v) => onCostPriceChange(Number(v) || 0)}
            />
          </Form.Item>
        </Col>
      </Row>
      <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--color-success-light)', borderRadius: 6 }}>
        利润：<span style={{ color: 'var(--color-success)', fontWeight: 600, fontSize: 16 }} className="tabular-nums">{formatMoney(profit)}</span>
      </div>
      <Form.Item name="channel" label="销售渠道">
        <Radio.Group value={channel} onChange={(e) => onChannelChange(e.target.value)}>
          <Radio.Button value="xianyu">闲鱼</Radio.Button>
          <Radio.Button value="wechat">微信</Radio.Button>
          <Radio.Button value="other">其他</Radio.Button>
        </Radio.Group>
      </Form.Item>
      {channel === 'xianyu' && (
        <Form.Item name="xianyu_order_no" label="闲鱼订单号（选填）">
          <Input placeholder="闲鱼订单号" />
        </Form.Item>
      )}
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item name="trade_at" label="交易时间">
            <DatePicker showTime style={{ width: '100%' }} value={tradeAt} onChange={(v) => v && onTradeAtChange(v)} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="status" label="交易状态">
            <Radio.Group value={status} onChange={(e) => onStatusChange(e.target.value)}>
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
          onChange={(v) => v && onShippedAtChange(v)}
        />
      </Form.Item>
    </Card>
  );
}
