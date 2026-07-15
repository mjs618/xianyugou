import { Modal, Form, Input, InputNumber, Select, DatePicker } from 'antd';

interface ExpenseModalProps {
  open: boolean;
  form: ReturnType<typeof Form.useForm>[0];
  submitting: boolean;
  onOk: () => void;
  onCancel: () => void;
}

/** 记录运营支出 Modal 表单。
 *
 * Form 实例由父组件传入（与「记擦亮费」按钮共享 setFieldsValue）。
 */
export default function ExpenseModal({ open, form, submitting, onOk, onCancel }: ExpenseModalProps) {
  return (
    <Modal
      title="记录运营支出"
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={submitting}
      okText="保存"
      cancelText="取消"
    >
      <Form form={form} layout="vertical">
        <Form.Item name="category" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
          <Select
            options={[
              { value: '擦亮', label: '擦亮' },
              { value: '推广', label: '推广' },
              { value: '平台服务', label: '平台服务' },
              { value: '其他', label: '其他' },
            ]}
          />
        </Form.Item>
        <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]}>
          <InputNumber min={0.01} precision={2} style={{ width: '100%' }} prefix="¥" />
        </Form.Item>
        <Form.Item name="occurred_at" label="发生时间" rules={[{ required: true, message: '请选择发生时间' }]}>
          <DatePicker showTime style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="notes" label="备注">
          <Input.TextArea rows={3} placeholder="可填写对应商品、账号或操作说明" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
