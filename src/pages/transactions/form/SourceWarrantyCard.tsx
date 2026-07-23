import { Card, Form, InputNumber, Radio, Switch } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import CustomerSelect from '@/components/CustomerSelect';
import { formatMoney } from '@/utils/format';
import type { SourceType } from '@/types';

interface SourceWarrantyCardProps {
  form: FormInstance;
  sourceType: SourceType;
  onSourceTypeChange: (s: SourceType) => void;
  customer?: { id?: number };
  hasWarranty: boolean;
  onWarrantyToggle: (checked: boolean) => void;
  warrantyDays: number;
  onWarrantyDaysChange: (v: number) => void;
  warrantyEnd?: Date;
  shippedAt: dayjs.Dayjs;
  expectedRebate: number;
  rebateBase: 'sale' | 'profit';
  rebateRate: number;
}

/** 来源与质保 Card：客户来源/介绍人/质保开关/质保周期/到期提示/预计返利。 */
export default function SourceWarrantyCard({
  form,
  sourceType,
  onSourceTypeChange,
  customer,
  hasWarranty,
  onWarrantyToggle,
  warrantyDays,
  onWarrantyDaysChange,
  warrantyEnd,
  shippedAt,
  expectedRebate,
  rebateBase,
  rebateRate,
}: SourceWarrantyCardProps) {
  return (
    <Card type="inner" title="来源与质保" size="small">
      <Form.Item name="source_type" label="客户来源">
        <Radio.Group value={sourceType} onChange={(e) => onSourceTypeChange(e.target.value)}>
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
        <Switch checked={hasWarranty} onChange={onWarrantyToggle} checkedChildren="质保" unCheckedChildren="不质保" />
      </Form.Item>

      {hasWarranty ? (
        <Form.Item name="warranty_days" label="质保周期（天）">
          <InputNumber min={1} max={3650} value={warrantyDays} onChange={(v) => onWarrantyDaysChange(Number(v) || 0)} style={{ width: 120 }} />
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
          <span style={{ color: 'var(--color-text-secondary)', marginLeft: 8 }}>（{rebateBase === 'profit' ? '利润' : '售价'} × {Math.round(rebateRate * 100)}%）</span>
        </div>
      )}
    </Card>
  );
}
