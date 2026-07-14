import { useEffect, useMemo, useState, useCallback } from 'react';
import DOMPurify from 'dompurify';
import { Card, Tabs, Form, Input, Button, Row, Col, Alert, Space, message, Tag, Divider, Typography, Select, Table, Popconfirm, Tooltip } from 'antd';
import { SendOutlined, ReloadOutlined, CopyOutlined, CheckCircleOutlined, CloseCircleOutlined, MailOutlined, DeleteOutlined, ThunderboltOutlined, HistoryOutlined, SnippetsOutlined } from '@ant-design/icons';
import { checkMailServer, sendDeliveryMail, buildDeliveryMail, parseDeliveryText, sendBatchDeliveryMail, type DeliveryInfo, type BatchResult } from '@/services/mailService';
import { listMailRecords, deleteMailRecord, clearMailRecords } from '@/services/mailRecordService';
import { searchCustomers } from '@/services/customerService';
import type { MailRecord, Customer } from '@/types';
import { BACKEND_POLL_INTERVAL_MS } from '@/config/constants';
import { getErrorMessage } from '@/utils/error';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Text } = Typography;

// 从 contact_info 提取邮箱
function extractEmail(contactInfo?: string): string {
  if (!contactInfo) return '';
  const m = contactInfo.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  return m ? m[0] : '';
}

interface MailFormValues {
  to: string;
  customerName?: string;
  email_account: string;
  gpt_password: string;
  token_url: string;
  email_password: string;
}

// ===== 单条发送 =====
function SingleSend({ checkServer }: { checkServer: () => Promise<boolean> }) {
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

  // 粘贴解析
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

  // 客户搜索
  const handleSearch = async (keyword: string) => {
    if (!keyword.trim()) return;
    setSearching(true);
    try {
      setCustomers(await searchCustomers(keyword));
    } finally {
      setSearching(false);
    }
  };

  // 选择客户
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
        {/* 粘贴快速解析 */}
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

          {/* 从客户记录导入 */}
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

// ===== 批量发送 =====
function BatchSend({ checkServer }: { checkServer: () => Promise<boolean> }) {
  const [batchText, setBatchText] = useState('');
  const [items, setItems] = useState<{ to: string; customerName?: string; delivery: DeliveryInfo }[]>([]);
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<BatchResult[]>([]);

  // 解析批量文本
  const handleParse = () => {
    const lines = batchText.split(/\r?\n/).filter((l) => l.trim());
    const parsed: { to: string; customerName?: string; delivery: DeliveryInfo }[] = [];
    for (const line of lines) {
      const parts = line.split(/[|\t]/).map((p) => p.trim());
      if (parts.length >= 5) {
        parsed.push({
          to: parts[0],
          delivery: {
            email_account: parts[1],
            gpt_password: parts[2],
            token_url: parts[3],
            email_password: parts[4],
          },
          customerName: parts[5] || undefined,
        });
      }
    }
    if (parsed.length === 0) {
      message.error('未能解析出有效数据，请检查格式（每行至少5个字段，用 | 分隔）');
      return;
    }
    setItems(parsed);
    setResults([]);
    message.success(`已解析 ${parsed.length} 条记录`);
  };

  const handleSend = async () => {
    if (items.length === 0) {
      message.warning('请先解析批量数据');
      return;
    }
    const online = await checkServer();
    if (!online) {
      message.error('邮件服务未运行，请先执行 npm run mail-server');
      return;
    }
    setSending(true);
    setResults([]);
    try {
      const r = await sendBatchDeliveryMail(items);
      setResults(r);
      const ok = r.filter((i) => i.success).length;
      message.success(`批量发送完成：成功 ${ok} 封，失败 ${r.length - ok} 封`);
    } catch (err: unknown) {
      message.error('批量发送异常：' + getErrorMessage(err, '未知错误'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="批量发送格式说明"
        description={
          <div>
            <p style={{ margin: '4px 0' }}>每行一条记录，字段用 <Text code>|</Text> 或制表符分隔，格式：</p>
            <Text code copyable>收件人邮箱|邮箱账号|GPT密码|动态令牌网址|邮箱密码|客户昵称(选填)</Text>
            <p style={{ margin: '4px 0', color: 'var(--color-text-secondary)', fontSize: 12 }}>
              示例：customer@example.com|BrittneyKailani791151@outlook.jp|KMoSo9P5T8Ess0P|https://2fa.run/xxx|ir75615777|张三
            </p>
          </div>
        }
      />
      <TextArea
        value={batchText}
        onChange={(e) => setBatchText(e.target.value)}
        placeholder={'每行一条记录，例如：\ncustomer1@example.com|BrittneyKailani791151@outlook.jp|KMoSo9P5T8Ess0P|https://2fa.run/xxx|ir75615777|张三\ncustomer2@example.com|AnotherUser@outlook.jp|Pass1234|https://2fa.run/yyy|pwd5678|李四'}
        rows={6}
        style={{ marginBottom: 12 }}
      />
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<SnippetsOutlined />} onClick={handleParse}>解析预览</Button>
        <Button type="primary" icon={<ThunderboltOutlined />} loading={sending} onClick={handleSend} disabled={items.length === 0}>
          批量发送（{items.length}）
        </Button>
        {items.length > 0 && <Button onClick={() => { setItems([]); setResults([]); }}>清空</Button>}
      </Space>

      {items.length > 0 && (
        <Table
          size="small"
          rowKey={(_, i) => String(i)}
          pagination={false}
          dataSource={items.map((item, i) => ({ ...item, index: i }))}
          columns={[
            { title: '#', dataIndex: 'index', width: 50, render: (i: number) => i + 1 },
            { title: '收件人', dataIndex: 'to', ellipsis: true, width: 180 },
            { title: '邮箱账号', dataIndex: ['delivery', 'email_account'], ellipsis: true },
            { title: '客户', dataIndex: 'customerName', width: 80 },
            {
              title: '状态', width: 100,
              render: (_: any, r: any) => {
                const res = results[r.index];
                if (!res) return <Tag>待发送</Tag>;
                return res.success
                  ? <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>
                  : <Tooltip title={res.error}><Tag icon={<CloseCircleOutlined />} color="error">失败</Tag></Tooltip>;
              },
            },
          ]}
        />
      )}
    </div>
  );
}

// ===== 发送历史 =====
function MailHistory() {
  const [records, setRecords] = useState<MailRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setRecords(await listMailRecords());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleResend = async (record: MailRecord) => {
    setSending(record.id!);
    try {
      const result = await sendDeliveryMail({
        to: record.to,
        customerName: record.customer_name,
        delivery: {
          email_account: record.email_account,
          gpt_password: record.gpt_password,
          token_url: record.token_url,
          email_password: record.email_password,
        },
      });
      if (result.success) {
        message.success(`已重新发送至 ${record.to}`);
        load();
      } else {
        message.error('重发失败：' + (result.error || '未知错误'));
      }
    } finally {
      setSending(null);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteMailRecord(id);
    message.success('已删除');
    load();
  };

  const handleClear = async () => {
    await clearMailRecords();
    message.success('已清空历史');
    load();
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
        <Text type="secondary">共 {records.length} 条记录</Text>
        {records.length > 0 && (
          <Popconfirm title="确定清空所有发送历史？" onConfirm={handleClear}>
            <Button size="small" danger icon={<DeleteOutlined />}>清空历史</Button>
          </Popconfirm>
        )}
      </div>
      <Table
        size="small"
        rowKey="id"
        loading={loading}
        dataSource={records}
        pagination={{ pageSize: 10 }}
        columns={[
          {
            title: '发送时间', dataIndex: 'sent_at', width: 160,
            render: (t: Date) => dayjs(t).format('YYYY-MM-DD HH:mm:ss'),
          },
          { title: '收件人', dataIndex: 'to', ellipsis: true, width: 180 },
          { title: '客户', dataIndex: 'customer_name', width: 80 },
          { title: '邮箱账号', dataIndex: 'email_account', ellipsis: true },
          {
            title: '状态', width: 90,
            render: (_: any, r: MailRecord) =>
              r.status === 'success'
                ? <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>
                : <Tooltip title={r.error}><Tag icon={<CloseCircleOutlined />} color="error">失败</Tag></Tooltip>,
          },
          {
            title: '操作', width: 140,
            render: (_: any, r: MailRecord) => (
              <Space>
                <Button size="small" type="link" loading={sending === r.id} onClick={() => handleResend(r)}>重发</Button>
                <Popconfirm title="确定删除此记录？" onConfirm={() => handleDelete(r.id!)}>
                  <Button size="small" type="link" danger>删除</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
    </div>
  );
}

// ===== 主页面 =====
export default function SendMail() {
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [activeTab, setActiveTab] = useState('single');

  const checkServer = useCallback(async () => {
    const ok = await checkMailServer();
    setServerOnline(ok);
    return ok;
  }, []);

  useEffect(() => {
    checkServer();
    const timer = setInterval(checkServer, BACKEND_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [checkServer]);

  return (
    <Card
      title={<span><MailOutlined /> 发货邮件</span>}
      extra={
        <Space>
          {serverOnline === null ? (
            <Tag color="default">检测中...</Tag>
          ) : serverOnline ? (
            <Tag icon={<CheckCircleOutlined />} color="success">邮件服务已连接</Tag>
          ) : (
            <Tag icon={<CloseCircleOutlined />} color="error">邮件服务未运行</Tag>
          )}
          <Button size="small" icon={<ReloadOutlined />} onClick={checkServer}>刷新</Button>
        </Space>
      }
    >
      {serverOnline === false && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="本地邮件服务未运行"
          description={
            <span>
              请在项目根目录新开一个终端，执行命令启动邮件服务：
              <Text code copyable style={{ marginLeft: 8 }}>npm run mail-server</Text>
            </span>
          }
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'single',
            label: <span><SendOutlined /> 单条发送</span>,
            children: <SingleSend checkServer={checkServer} />,
          },
          {
            key: 'batch',
            label: <span><ThunderboltOutlined /> 批量发送</span>,
            children: <BatchSend checkServer={checkServer} />,
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> 发送历史</span>,
            children: <MailHistory />,
          },
        ]}
      />
    </Card>
  );
}
