import { Card, Form, Input, Radio, Tag } from 'antd';
import type { FormInstance } from 'antd';
import CustomerSelect from '@/components/CustomerSelect';
import { formatMoney } from '@/utils/format';
import type { Customer } from '@/types';

interface CustomerInfoCardProps {
  form: FormInstance;
  isNewCustomer: boolean;
  onToggleNewCustomer: (val: boolean) => void;
  newNickname: string;
  onNewNicknameChange: (val: string) => void;
  customer?: Customer;
  onCustomerChange: (c?: Customer) => void;
}

/** 客户信息 Card：选择老客户或新建客户，显示累计消费/等级/黑名单。 */
export default function CustomerInfoCard({
  form,
  isNewCustomer,
  onToggleNewCustomer,
  newNickname,
  onNewNicknameChange,
  customer,
  onCustomerChange,
}: CustomerInfoCardProps) {
  return (
    <Card type="inner" title="客户信息" size="small">
      <Form.Item label="客户选择方式">
        <Radio.Group value={isNewCustomer} onChange={(e) => onToggleNewCustomer(e.target.value)}>
          <Radio.Button value={false}>选择老客户</Radio.Button>
          <Radio.Button value={true}>新建客户</Radio.Button>
        </Radio.Group>
      </Form.Item>

      {isNewCustomer ? (
        <>
          <Form.Item label="闲鱼昵称" required>
            <Input placeholder="输入新客户闲鱼昵称" value={newNickname} onChange={(e) => onNewNicknameChange(e.target.value)} />
          </Form.Item>
          <Form.Item name="contact_info" label="联系方式（选填）">
            <Input placeholder="微信/手机号" />
          </Form.Item>
        </>
      ) : (
        <>
          <Form.Item name="customer_id" label="闲鱼昵称" rules={[{ required: true, message: '请选择客户' }]}>
            <CustomerSelect value={undefined} onChange={(_v, c) => onCustomerChange(c)} />
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
  );
}
