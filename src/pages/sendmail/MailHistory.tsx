import { useEffect, useState } from 'react';
import { Button, Popconfirm, Space, Table, Tag, Tooltip, Typography, message } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { sendDeliveryMail } from '@/services/mailService';
import { listMailRecords, deleteMailRecord, clearMailRecords } from '@/services/mailRecordService';
import type { MailRecord } from '@/types';

const { Text } = Typography;

/** 发送历史：列表展示已发送记录，支持重发、删除、清空。 */
export default function MailHistory() {
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
