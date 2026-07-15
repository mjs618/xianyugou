import { useMemo, useState } from 'react';
import DOMPurify from 'dompurify';
import { Card, Form, Input, Button, Row, Col, Divider, Space, message, Select } from 'antd';
import { SendOutlined, ReloadOutlined, CopyOutlined, SnippetsOutlined, MailOutlined } from '@ant-design/icons';
import { checkMailServer, sendDeliveryMail, buildDeliveryMail, parseDeliveryText, type DeliveryInfo } from '@/services/mailService';
import { searchCustomers } from '@/services/customerService';
import type { Customer } from '@/types';
import { getErrorMessage } from '@/utils/error';
import { extractEmail, type MailFormValues } from './shared';

const { TextArea } = Input;

/** 单条发送：表单填写 + 粘贴快速解析 + 实时预览。 */
export default function SingleSend({ checkServer }: { checkServer: () => Promise<boolean> }) {
  const [form] = Form.useForm<MailFormValues>();
  const [sending, setSending] = useState(false);
  const [values, setValues] = useState<MailFormValues | null>(null);
  const [pasteText, setPasteText] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [searching, setSearching] = useState(false);

  const handleValuesChange = (_changed: unknown, all: MailFormValues) => {
    setValues(all);
  };

  const preview = useMemo(() => {
    if (!values?.email_account && !values?.gpt_password && !values?.token_url && !values?.email_password) {
      return null;
    }
    const delivery: DeliveryInfo = {
      email_account: values?.email_account || '',
      gpt_password: values?.gpt_password || '',
      token_url: values?.token_url || '',
      email_password: values?.email_password || '',
    };
    return buildDeliveryMail(delivery, values?.customerName);
  }, [values]);

  const handleParse = () => {
    if (!pasteText.trim()) {
      message.warning('请先粘贴发货信息文本');
      return;
    }
    const parsed = parseDeliveryText(pasteText);
    const current = form.getFieldsValue();
    form.setFieldsValue({
      ...current,
      email_account: parsed.email_account || current.email_account,
      gpt_password: parsed.gpt_password || current.gpt_password,
      token_url: parsed.token_url || current.token_url,
      email_password: parsed.email_password || current.email_password,
    });
    setValues(form.getFieldsValue());
    const filled = Object.values(parsed).filter(Boolean).length;
    message.success(`已解析 ${filled} 个字段`);
  };

  const handleSearch = async (keyword: string) => {
    if (!keyword.trim()) return;
    setSearching(true);
    try {
      setCustomers(await searchCustomers(keyword));
    } finally {
      setSearching(false);
    }
  };

  const handleSelectCustomer = (customerId: number) => {
    const c = customers.find((x) => x.id === customerId);
    if (!c) return;
    const email = extractEmail(c.contact_info);
    const current = form.getFieldsValue();
    form.setFieldsValue({
      ...current,
      to: email || current.to,
      customerName: c.xianyu_nickname,
    });
    setValues(form.getFieldsValue());
    if (!email) {
      message.info('该客户联系方式中未找到邮箱，请手动填写收件人邮箱');
    }
  };

  const handleSend = async () => {
    const v = await form.validateFields();
    const online = await checkServer();
    if (!online) {
      message.error('邮件服务未运行，请先在终端执行 npm run mail-server');
      return;
    }
    setSending(true);
    try {
      const result = await sendDeliveryMail({
        to: v.to,
        customerName: v.customerName,
        delivery: {
          email_account: v.email_account,
          gpt_password: v.gpt_password,
          token_url: v.token_url,
          email_password: v.email_password,
        },
      });
      if (result.success) {
        message.success(`邮件已发送至 ${v.to}`);
        form.resetFields();
        setValues(null);
        setPasteText('');
      } else {
        message.error('发送失败：' + (result.error || '未知错误'));
      }
    } catch (err: unknown) {
      message.error('发送异常：' + getErrorMessage(err, '未知错误'));
    } finally {
      setSending(false);
    }
  };

  const handleCopyText = async () => {
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(preview.text);
      message.success('纯文本内容已复制');
    } catch {
      message.error('复制失败');
    }
  };

  const handleReset = () => {
    form.resetFields();
    setValues(null);
    setPasteText('');
  };

  return (
    <Row gutter={20}>
      <Col xs={24} lg={11}>
        <Card size="small" title={<span><SnippetsOutlined /> 粘贴快速解析</span>} style={{ marginBottom: 16 }}>
          <TextArea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder={'粘贴发货信息文本，自动识别字段，例如：\n邮箱账号：BrittneyKailani791151@outlook.jp\nGPT 密码：KMoSo9P5T8Ess0P\n动态令牌网址：https://2fa.run/2fa/OYNSN7BW\n邮箱密码：ir75615777'}
            rows={4}
            style={{ marginBottom: 8 }}
          />
          <Button type="primary" ghost icon={<SnippetsOutlined />} onClick={handleParse}>解析填充</Button>
        </Card>

        <Form form={form} layout="vertical" onValuesChange={handleValuesChange} requiredMark>
          <Divider orientation="left" plain style={{ fontSize: 13 }}>客户信息</Divider>

          <Form.Item label="从客户记录导入（选填）">
            <Select
              showSearch
              placeholder="搜索客户昵称或联系方式"
              filterOption={false}
              onSearch={handleSearch}
              loading={searching}
              onChange={handleSelectCustomer}
              allowClear
              notFoundContent={searching ? '搜索中...' : '输入关键词搜索客户'}
              options={customers.map((c) => ({
                value: c.id,
                label: `${c.xianyu_nickname}${c.contact_info ? '（' + c.contact_info + '）' : ''}`,
              }))}
            />
          </Form.Item>

          <Form.Item name="to" label="收件人邮箱" rules={[{ required: true, message: '请输入收件人邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}>
            <Input placeholder="如：customer@example.com" />
          </Form.Item>
          <Form.Item name="customerName" label="客户昵称（选填）">
            <Input placeholder="如：张三" />
          </Form.Item>

          <Divider orientation="left" plain style={{ fontSize: 13 }}>商品信息（GPT 账号）</Divider>
          <Form.Item name="email_account" label="邮箱账号" rules={[{ required: true, message: '请输入邮箱账号' }]}>
            <Input placeholder="如：BrittneyKailani791151@outlook.jp" />
          </Form.Item>
          <Form.Item name="gpt_password" label="GPT 密码" rules={[{ required: true, message: '请输入 GPT 密码' }]}>
            <Input placeholder="如：KMoSo9P5T8Ess0P" />
          </Form.Item>
          <Form.Item name="token_url" label="动态令牌网址" rules={[{ required: true, message: '请输入动态令牌网址' }]}>
            <Input placeholder="如：https://2fa.run/2fa/OYNSN7BW..." />
          </Form.Item>
          <Form.Item name="email_password" label="邮箱密码" rules={[{ required: true, message: '请输入邮箱密码' }]}>
            <Input placeholder="如：ir75615777" />
          </Form.Item>

          <Space>
            <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend}>发送邮件</Button>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>清空</Button>
          </Space>
        </Form>
      </Col>

      <Col xs={24} lg={13}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ margin: 0, color: 'var(--color-dark)' }}>邮件预览</h3>
          {preview && <Button size="small" icon={<CopyOutlined />} onClick={handleCopyText}>复制纯文本</Button>}
        </div>
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 8, minHeight: 400, maxHeight: 600, overflow: 'auto', padding: 16, background: 'var(--color-surface)' }}>
          {preview ? (
            <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(preview.html) }} />
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--color-text-tertiary)', paddingTop: 120 }}>
              <MailOutlined style={{ fontSize: 40, marginBottom: 12 }} />
              <div>填写左侧发货信息后，此处将实时预览邮件内容</div>
            </div>
          )}
        </div>
      </Col>
    </Row>
  );
}
