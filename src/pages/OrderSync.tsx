import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Space, Modal, Input, Form, message, Popconfirm,
  Tag, Alert, Descriptions, Empty, Tooltip, Result, Spin,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined, CloudSyncOutlined,
  CheckCircleOutlined, ApiOutlined, LinkOutlined, HistoryOutlined, SyncOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import {
  listAccounts, createAccount, updateAccount, deleteAccount, testAccount,
  syncOrders, listOrders, listSyncLogs, checkBackend,
} from '@/services/xianyuService';
import type { XianyuAccount, XianyuOrder, XianyuSyncResult, XianyuSyncLog } from '@/types';

const { TextArea } = Input;
const { Text } = { Text: (props: any) => <span {...props} /> };

// 账号状态标签
function StatusTag({ status }: { status: string }) {
  const map: Record<string, { text: string; color: string }> = {
    online: { text: '在线', color: 'green' },
    invalid: { text: '失效', color: 'red' },
    risk: { text: '风控', color: 'orange' },
  };
  const cfg = map[status] || { text: status, color: 'default' };
  return <Tag color={cfg.color} icon={<CheckCircleOutlined />}>{cfg.text}</Tag>;
}

export default function OrderSync() {
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<XianyuAccount | null>(null);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<XianyuSyncResult | null>(null);
  const [logModalId, setLogModalId] = useState<number | null>(null);
  const [syncLogs, setSyncLogs] = useState<XianyuSyncLog[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [orderModalId, setOrderModalId] = useState<number | null>(null);
  const [mirrorOrders, setMirrorOrders] = useState<XianyuOrder[]>([]);
  const [orderLoading, setOrderLoading] = useState(false);
  const [form] = Form.useForm();

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      setAccounts(await listAccounts());
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载账号失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const checkStatus = useCallback(async () => {
    setBackendOnline(await checkBackend());
  }, []);

  useEffect(() => {
    loadAccounts();
    checkStatus();
    // 轮询后端状态（每 15 秒，与 SendMail 一致）
    const timer = setInterval(checkStatus, 15000);
    return () => clearInterval(timer);
  }, [loadAccounts, checkStatus]);

  // 加载同步日志
  useEffect(() => {
    if (logModalId !== null) {
      setLogLoading(true);
      listSyncLogs(logModalId)
        .then(setSyncLogs)
        .catch(() => message.error('加载同步日志失败'))
        .finally(() => setLogLoading(false));
    }
  }, [logModalId]);

  // 加载订单镜像
  useEffect(() => {
    if (orderModalId !== null) {
      setOrderLoading(true);
      listOrders(orderModalId)
        .then(setMirrorOrders)
        .catch(() => message.error('加载订单镜像失败'))
        .finally(() => setOrderLoading(false));
    }
  }, [orderModalId]);

  const handleCreateOrUpdate = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateAccount(editing.id, { nickname: values.nickname, cookies: values.cookies });
        message.success('账号已更新');
      } else {
        await createAccount({ nickname: values.nickname, cookies: values.cookies });
        message.success('账号已添加');
      }
      setModalOpen(false);
      form.resetFields();
      setEditing(null);
      loadAccounts();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteAccount(id);
      message.success('已删除');
      loadAccounts();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleTest = async (id: number) => {
    try {
      const result = await testAccount(id);
      if (result.valid) {
        message.success(`Cookie 有效（用户ID: ${result.unb}）`);
      } else {
        message.warning(result.message);
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '校验失败');
    }
  };

  const handleSync = async (id: number) => {
    setSyncingId(id);
    setLastSyncResult(null);
    try {
      const result = await syncOrders(id);
      setLastSyncResult(result);
      if (result.success) {
        message.success(`同步完成：拉取 ${result.fetched} 单，新增 ${result.created_count} 笔，跳过 ${result.skipped_count} 笔`);
      } else {
        message.warning(`同步未完成：${result.error || '未知原因'}（已写入 ${result.created_count} 笔）`);
      }
      loadAccounts();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '同步失败');
    } finally {
      setSyncingId(null);
    }
  };

  const columns: ColumnsType<XianyuAccount> = [
    {
      title: '账号', dataIndex: 'nickname', width: 160,
      render: (v: string, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{v}</Text>
          {r.unb && <Text style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>ID: {r.unb}</Text>}
        </Space>
      ),
    },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <StatusTag status={v} />,
    },
    {
      title: '上次同步', dataIndex: 'last_sync_at', width: 160,
      render: (v?: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : <Text style={{ color: 'var(--color-text-tertiary)' }}>从未同步</Text>,
    },
    {
      title: '最近错误', dataIndex: 'last_error', ellipsis: true,
      render: (v?: string) => v ? (
        <Tooltip title={v}><Text type="danger" style={{ fontSize: 12 }}>{v}</Text></Tooltip>
      ) : <Text style={{ color: 'var(--color-text-tertiary)' }}>-</Text>,
    },
    {
      title: '操作', width: 320, fixed: 'right',
      render: (_: unknown, r: XianyuAccount) => (
        <Space size={4} wrap>
          <Button
            type="primary" size="small" icon={<SyncOutlined />}
            loading={syncingId === r.id}
            onClick={() => handleSync(r.id)}
          >同步订单</Button>
          <Button size="small" icon={<ApiOutlined />} onClick={() => handleTest(r.id)}>校验</Button>
          <Button size="small" icon={<CloudSyncOutlined />} onClick={() => setOrderModalId(r.id)}>镜像</Button>
          <Button size="small" icon={<HistoryOutlined />} onClick={() => setLogModalId(r.id)}>日志</Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => { setEditing(r); form.setFieldsValue({ nickname: r.nickname }); setModalOpen(true); }} />
          <Popconfirm title="确认删除该账号？" onConfirm={() => handleDelete(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 后端离线提示
  if (backendOnline === false) {
    return (
      <Card title={<span><CloudSyncOutlined /> 订单同步</span>}>
        <Result
          status="warning"
          title="后端服务未启动"
          subTitle={
            <span>
              订单同步依赖后端服务（Python FastAPI）。请在 <Text code>server/backend</Text> 目录运行启动命令。
              <br />启动后此页面将自动恢复可用。
            </span>
          }
          extra={<Button type="primary" icon={<ReloadOutlined />} onClick={checkStatus}>重新检测</Button>}
        />
      </Card>
    );
  }

  if (backendOnline === null) {
    return (
      <Card title={<span><CloudSyncOutlined /> 订单同步</span>}>
        <div style={{ textAlign: 'center', padding: 60 }}><Spin tip="检测后端服务..." /></div>
      </Card>
    );
  }

  const emptyText = <Empty description="暂无闲鱼账号，点击「添加账号」开始" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  return (
    <Card
      title={<span><CloudSyncOutlined /> 订单同步</span>}
      extra={
        <Space>
          <Tag color="green" icon={<CheckCircleOutlined />}>后端已连接</Tag>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}>
            添加账号
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadAccounts}>刷新</Button>
        </Space>
      }
    >
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="订单同步说明"
        description={
          <span>
            添加闲鱼账号后，点击「同步订单」即可自动拉取成交订单并写入交易记录（自动建立客户、计算利润、生成质保）。
            同步按订单号去重，可安全重复执行。
            <br />
            <Text style={{ fontSize: 12 }}>
              <LinkOutlined /> 获取 Cookie：在浏览器登录闲鱼（goofish.com）后，打开开发者工具 → Network → 任意请求 → 复制完整 Cookie。
            </Text>
          </span>
        }
      />

      {lastSyncResult && (
        <Alert
          type={lastSyncResult.success ? 'success' : 'warning'}
          showIcon closable onClose={() => setLastSyncResult(null)}
          style={{ marginBottom: 16 }}
          message={lastSyncResult.success ? '同步完成' : '同步未完全成功'}
          description={`拉取 ${lastSyncResult.fetched} 单 · 新增 ${lastSyncResult.created_count} 笔 · 跳过 ${lastSyncResult.skipped_count} 笔${lastSyncResult.error ? ` · 错误：${lastSyncResult.error}` : ''}`}
        />
      )}

      <Table
        rowKey="id" size="middle"
        dataSource={accounts} columns={columns}
        loading={loading}
        pagination={false}
        locale={{ emptyText }}
        scroll={{ x: 800 }}
      />

      {/* 添加 / 编辑账号 Modal */}
      <Modal
        title={editing ? '更新账号 Cookie' : '添加闲鱼账号'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditing(null); form.resetFields(); }}
        onOk={handleCreateOrUpdate}
        okText={editing ? '更新' : '添加'}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="nickname" label="账号备注" rules={[{ required: true, message: '请输入账号备注名' }]}>
            <Input placeholder="如：主号 / 副号" />
          </Form.Item>
          <Form.Item
            name="cookies"
            label="闲鱼 Cookie"
            rules={[{ required: true, message: '请粘贴 Cookie' }]}
            extra="粘贴登录闲鱼后复制的完整 Cookie 字符串。必须包含 unb（用户ID）和 _m_h5_tk 字段。Cookie 将加密存储，不会明文显示。"
          >
            <TextArea
              rows={6}
              placeholder="在此粘贴 Cookie，格式如：unb=xxxx; _m_h5_tk=xxxx_timestamp; cookie2=xxxx; ..."
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 订单镜像 Modal */}
      <Modal
        title="订单镜像"
        open={orderModalId !== null}
        onCancel={() => setOrderModalId(null)}
        footer={null}
        width={900}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="这里展示的是闲鱼订单镜像摘要，不包含平台原始响应 raw_order。"
        />
        <Table
          rowKey="id" size="small"
          loading={orderLoading}
          dataSource={mirrorOrders}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无订单镜像" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            {
              title: '订单号', dataIndex: 'order_no', width: 150,
              render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
            },
            { title: '买家', dataIndex: 'buyer_nick', width: 120, render: (v?: string) => v || '-' },
            { title: '商品', dataIndex: 'product_name', ellipsis: true, render: (v?: string) => v || '-' },
            {
              title: '状态', dataIndex: 'order_status', width: 110,
              render: (v?: string) => v ? <Tag>{v}</Tag> : '-',
            },
            {
              title: '金额', dataIndex: 'sale_price', width: 90, align: 'right' as const,
              render: (v: number) => `¥${Number(v || 0).toFixed(2)}`,
            },
            {
              title: '交易时间', dataIndex: 'trade_at', width: 150,
              render: (v?: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
            },
            {
              title: '最近同步', dataIndex: 'last_seen_at', width: 150,
              render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
            },
          ]}
        />
      </Modal>

      {/* 同步日志 Modal */}
      <Modal
        title="同步日志"
        open={logModalId !== null}
        onCancel={() => setLogModalId(null)}
        footer={null}
        width={720}
      >
        <Table
          rowKey="id" size="small"
          loading={logLoading}
          dataSource={syncLogs}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无同步记录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            {
              title: '时间', dataIndex: 'created_at', width: 150,
              render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
            },
            {
              title: '状态', dataIndex: 'status', width: 80,
              render: (v: string) => v === 'success'
                ? <Tag color="green">成功</Tag>
                : <Tag color="red">失败</Tag>,
            },
            { title: '拉取', dataIndex: 'fetched', width: 70, align: 'center' as const },
            { title: '新增', dataIndex: 'created_count', width: 70, align: 'center' as const, render: (v: number) => <Text type="success">{v}</Text> },
            { title: '跳过', dataIndex: 'skipped_count', width: 70, align: 'center' as const },
            {
              title: '错误', dataIndex: 'error', ellipsis: true,
              render: (v?: string) => v ? <Text type="danger" style={{ fontSize: 12 }}>{v}</Text> : '-',
            },
          ]}
        />
      </Modal>
    </Card>
  );
}
