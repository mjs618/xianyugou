import { useState } from 'react';
import { Alert, Button, Space, Table, Tag, Tooltip, Typography, message, Input } from 'antd';
import {
  SnippetsOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { sendBatchDeliveryMail, type DeliveryInfo, type BatchResult } from '@/services/mailService';
import { getErrorMessage } from '@/utils/error';

const { Text } = Typography;
const { TextArea } = Input;

/** 批量发送：粘贴多行文本解析 + 表格预览 + 一键批量发送。 */
export default function BatchSend({ checkServer }: { checkServer: () => Promise<boolean> }) {
  const [batchText, setBatchText] = useState('');
  const [items, setItems] = useState<{ to: string; customerName?: string; delivery: DeliveryInfo }[]>([]);
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<BatchResult[]>([]);

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
