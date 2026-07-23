import { Button, Col, Form, InputNumber, Row, Select, message } from 'antd';
import type { FormInstance } from 'antd';
import { updateSettings } from '@/services/settingsService';
import { getErrorMessage, isValidationError } from '@/utils/error';
import { useAppStore } from '@/store/useAppStore';

interface SystemSettingsTabProps {
  /** 容器共享的 settingsForm 实例（loadSettings 也会写入此 form）。 */
  form: FormInstance;
  /** 保存成功后调用容器的 loadSettings + refreshAll，回填两个表单并刷新顶部统计。 */
  onSaved: () => Promise<void>;
}

/** 系统设置 Tab：质保周期 / 返利比例 / VIP 阈值 / 回访提醒间隔。
 *
 * Form 实例由容器传入（与 loadSettings 共享），子组件自身无 state。
 * Form 实例是 ref 对象，值在实例内持久；子组件因 Tab 切换卸载后重挂载时，
 * `<Form form={form}>` 会重连实例并恢复字段值（antd Form 行为）。
 */
export default function SystemSettingsTab({ form, onSaved }: SystemSettingsTabProps) {
  const { refreshAll } = useAppStore();

  const handleSaveSettings = async () => {
    try {
      const values = await form.validateFields();
      await updateSettings(values);
      message.success('设置已保存');
      refreshAll();
      await onSaved();
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      console.error('保存设置失败:', err);
      message.error(getErrorMessage(err, '保存失败'));
    }
  };

  return (
    <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
      <Form.Item name="warranty_days" label="默认质保周期（天）" tooltip="填 0 表示新订单默认不质保" rules={[{ required: true }]}>
        <InputNumber min={0} max={3650} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item name="rebate_rate" label="返利比例（0-1，如0.1表示10%）" rules={[{ required: true }]}>
        <InputNumber min={0} max={1} step={0.01} precision={2} style={{ width: '100%' }} />
      </Form.Item>
      <Form.Item name="rebate_base" label="返利基数" rules={[{ required: true }]}>
        <Select
          options={[
            { value: 'profit', label: '利润（默认）' },
            { value: 'sale', label: '售价' },
          ]}
        />
      </Form.Item>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="vip_threshold" label="VIP 金额阈值（元）" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="vip_trade_count" label="VIP 笔数阈值" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="core_threshold" label="核心客户金额阈值（元）" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="core_trade_count" label="核心客户笔数阈值" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item name="recall_days" label="客户回访提醒间隔（天）" rules={[{ required: true }]}>
        <InputNumber min={1} max={365} style={{ width: '100%' }} />
      </Form.Item>
      <Button type="primary" onClick={handleSaveSettings}>保存设置</Button>
    </Form>
  );
}
