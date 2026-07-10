import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Space, Modal, Input, Form, message, Popconfirm,
  Tag, Alert, Descriptions, Empty, Tooltip, Result, Spin, Segmented,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined, CloudSyncOutlined,
  CheckCircleOutlined, ApiOutlined, LinkOutlined, HistoryOutlined, SyncOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import {
  listAccounts, createAccount, updateAccount, deleteAccount, testAccount,
  syncOrders, listOrders, listSyncLogs, checkBackend, formatSyncResultMessage,
  hasSyncedOrdersToView, summarizeXianyuOrders, filterXianyuOrdersByProjection,
  syncItems, listItems, formatItemSyncResultMessage, hasSyncedItemsToView,
  summarizeXianyuItems, filterXianyuItemsByTemplateProjection, getCookieCloudConfigStatus,
  formatXianyuOrderProjectionSummary,
} from '@/services/xianyuService';
import type { XianyuItemTemplateProjectionFilter, XianyuOrderProjectionFilter } from '@/services/xianyuService';
import type {
  XianyuAccount,
  CookieCloudConfigStatus,
  XianyuItem,
  XianyuItemSyncResult,
  XianyuOrder,
  XianyuSyncResult,
  XianyuSyncLog,
} from '@/types';

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
  const [cookieCloudStatus, setCookieCloudStatus] = useState<CookieCloudConfigStatus | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<XianyuAccount | null>(null);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<XianyuSyncResult | null>(null);
  const [lastSyncAccountId, setLastSyncAccountId] = useState<number | null>(null);
  const [logModalId, setLogModalId] = useState<number | null>(null);
  const [syncLogs, setSyncLogs] = useState<XianyuSyncLog[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [orderModalId, setOrderModalId] = useState<number | null>(null);
  const [mirrorOrders, setMirrorOrders] = useState<XianyuOrder[]>([]);
  const [orderProjectionFilter, setOrderProjectionFilter] = useState<XianyuOrderProjectionFilter>('all');
  const [orderLoading, setOrderLoading] = useState(false);
  const [itemSyncingId, setItemSyncingId] = useState<number | null>(null);
  const [lastItemSyncResult, setLastItemSyncResult] = useState<XianyuItemSyncResult | null>(null);
  const [lastItemSyncAccountId, setLastItemSyncAccountId] = useState<number | null>(null);
  const [itemModalId, setItemModalId] = useState<number | null>(null);
  const [itemMirrors, setItemMirrors] = useState<XianyuItem[]>([]);
  const [itemTemplateFilter, setItemTemplateFilter] = useState<XianyuItemTemplateProjectionFilter>('all');
  const [itemLoading, setItemLoading] = useState(false);
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

  const loadCookieCloudStatus = useCallback(async () => {
    try {
      setCookieCloudStatus(await getCookieCloudConfigStatus());
    } catch {
      setCookieCloudStatus(null);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
    checkStatus();
    loadCookieCloudStatus();
    // 轮询后端状态（每 15 秒，与 SendMail 一致）
    const timer = setInterval(checkStatus, 15000);
    return () => clearInterval(timer);
  }, [loadAccounts, checkStatus, loadCookieCloudStatus]);

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

  // 加载商品镜像
  useEffect(() => {
    if (itemModalId !== null) {
      setItemLoading(true);
      listItems(itemModalId)
        .then(setItemMirrors)
        .catch(() => message.error('加载商品镜像失败'))
        .finally(() => setItemLoading(false));
    }
  }, [itemModalId]);

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
    setLastSyncAccountId(null);
    try {
      const result = await syncOrders(id);
      setLastSyncResult(result);
      setLastSyncAccountId(id);
      if (result.success) {
        message.success(formatSyncResultMessage(result));
      } else {
        message.warning(formatSyncResultMessage(result));
      }
      loadAccounts();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '同步失败');
    } finally {
      setSyncingId(null);
    }
  };

  const handleSyncItems = async (id: number) => {
    setItemSyncingId(id);
    setLastItemSyncResult(null);
    setLastItemSyncAccountId(null);
    try {
      const result = await syncItems(id);
      setLastItemSyncResult(result);
      setLastItemSyncAccountId(id);
      if (result.success) {
        message.success(formatItemSyncResultMessage(result));
      } else {
        message.warning(formatItemSyncResultMessage(result));
      }
      if (hasSyncedItemsToView(result)) {
        setItemTemplateFilter('all');
        setItemModalId(id);
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '商品同步失败');
    } finally {
      setItemSyncingId(null);
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
      title: '操作', width: 440, fixed: 'right',
      render: (_: unknown, r: XianyuAccount) => (
        <Space size={4} wrap>
          <Button
            type="primary" size="small" icon={<SyncOutlined />}
            loading={syncingId === r.id}
            onClick={() => handleSync(r.id)}
          >同步订单</Button>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={itemSyncingId === r.id}
            onClick={() => handleSyncItems(r.id)}
          >同步商品</Button>
          <Button size="small" icon={<ApiOutlined />} onClick={() => handleTest(r.id)}>校验</Button>
          <Button size="small" icon={<CloudSyncOutlined />} onClick={() => { setOrderProjectionFilter('all'); setOrderModalId(r.id); }}>订单镜像</Button>
          <Button size="small" icon={<CloudSyncOutlined />} onClick={() => { setItemTemplateFilter('all'); setItemModalId(r.id); }}>商品镜像</Button>
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
  const mirrorSummary = summarizeXianyuOrders(mirrorOrders);
  const filteredMirrorOrders = filterXianyuOrdersByProjection(mirrorOrders, orderProjectionFilter);
  const itemSummary = summarizeXianyuItems(itemMirrors);
  const filteredItemMirrors = filterXianyuItemsByTemplateProjection(itemMirrors, itemTemplateFilter);

  return (
    <Card
      title={<span><CloudSyncOutlined /> 订单同步</span>}
      extra={
        <Space>
          <Tag color="green" icon={<CheckCircleOutlined />}>后端已连接</Tag>
          {cookieCloudStatus && (
            <Tag color={cookieCloudStatus.enabled ? 'green' : 'orange'} icon={<CloudSyncOutlined />}>
              {cookieCloudStatus.enabled ? 'CookieCloud 已启用' : 'CookieCloud 未启用'}
            </Tag>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}>
            添加账号
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadAccounts}>刷新</Button>
        </Space>
      }
    >
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="闲鱼同步说明"
        description={
          <span>
            添加闲鱼账号后，点击「同步订单」即可自动拉取成交订单并写入交易记录（自动建立客户、计算利润、生成质保）。
            点击「同步商品」会拉取该账号的在售/历史商品摘要，生成商品镜像；需要导入为商品模板时，可到「设置 / 商品模板 / 从闲鱼导入商品」批量导入。
            同步按订单号去重，可安全重复执行。
            <br />
            <Text style={{ fontSize: 12 }}>
              <LinkOutlined /> 获取 Cookie：在浏览器登录闲鱼（goofish.com）后，打开开发者工具 → Network → 任意请求 → 复制完整 Cookie。
            </Text>
          </span>
        }
      />

      {cookieCloudStatus && (
        <Alert
          type={cookieCloudStatus.enabled ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 16 }}
          message={cookieCloudStatus.enabled ? 'Cookie 过期后会尝试自动续 Cookie' : 'Cookie 过期后不会自动续 Cookie'}
          description={
            <span>
              {cookieCloudStatus.message}
              <br />
              <Text style={{ fontSize: 12 }}>
                {cookieCloudStatus.next_step}
                {!cookieCloudStatus.enabled && cookieCloudStatus.missing_keys.length > 0
                  ? ` 缺少配置：${cookieCloudStatus.missing_keys.join('、')}`
                  : ''}
              </Text>
            </span>
          }
          action={<Button size="small" onClick={loadCookieCloudStatus}>重新检测</Button>}
        />
      )}

      {lastSyncResult && (
        <Alert
          type={lastSyncResult.success ? 'success' : 'warning'}
          showIcon closable onClose={() => setLastSyncResult(null)}
          style={{ marginBottom: 16 }}
          message={lastSyncResult.success ? '同步完成' : '同步未完全成功'}
          description={formatSyncResultMessage(lastSyncResult)}
          action={
            lastSyncAccountId !== null && hasSyncedOrdersToView(lastSyncResult)
              ? (
                <Button size="small" onClick={() => { setOrderProjectionFilter('all'); setOrderModalId(lastSyncAccountId); }}>
                  查看镜像订单
                </Button>
              )
              : undefined
          }
        />
      )}

      <Table
        rowKey="id" size="middle"
        dataSource={accounts} columns={columns}
        loading={loading}
        pagination={false}
        locale={{ emptyText }}
        scroll={{ x: 980 }}
      />

      {lastItemSyncResult && (
        <Alert
          type={lastItemSyncResult.success ? 'success' : 'warning'}
          showIcon
          closable
          onClose={() => setLastItemSyncResult(null)}
          style={{ marginTop: 16 }}
          message={lastItemSyncResult.success ? '商品同步完成' : '商品同步未完全成功'}
          description={formatItemSyncResultMessage(lastItemSyncResult)}
          action={
            lastItemSyncAccountId !== null && hasSyncedItemsToView(lastItemSyncResult)
              ? (
                <Button size="small" onClick={() => { setItemTemplateFilter('all'); setItemModalId(lastItemSyncAccountId); }}>
                  查看商品镜像
                </Button>
              )
              : undefined
          }
        />
      )}

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
            extra={
              cookieCloudStatus?.enabled
                ? '粘贴登录闲鱼后复制的完整 Cookie 字符串。Cookie 将加密存储；后续过期时会尝试通过 CookieCloud 自动续 Cookie。'
                : `粘贴登录闲鱼后复制的完整 Cookie 字符串。必须包含 unb（用户ID）和 _m_h5_tk 字段。Cookie 将加密存储；当前 CookieCloud 未启用，过期后需手动更新${cookieCloudStatus?.missing_keys.length ? `（缺少 ${cookieCloudStatus.missing_keys.join('、')}）` : ''}。`
            }
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
          description={formatXianyuOrderProjectionSummary(mirrorSummary)}
          message="这里展示的是闲鱼订单镜像摘要，不包含平台原始响应 raw_order。"
        />
        <Segmented
          size="small"
          value={orderProjectionFilter}
          onChange={(value) => setOrderProjectionFilter(value as XianyuOrderProjectionFilter)}
          options={[
            { label: '全部', value: 'all' },
            { label: '已生成交易', value: 'projected' },
            { label: '未生成交易', value: 'unprojected' },
          ]}
          style={{ marginBottom: 12 }}
        />
        <Table
          rowKey="id" size="small"
          loading={orderLoading}
          dataSource={filteredMirrorOrders}
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
              title: '投影', dataIndex: 'projected_transaction_id', width: 90,
              render: (v?: number) => v
                ? <Tag color="green">已生成</Tag>
                : <Tag>未生成</Tag>,
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

      {/* 商品镜像 Modal */}
      <Modal
        title="商品镜像"
        open={itemModalId !== null}
        onCancel={() => setItemModalId(null)}
        footer={[
          <Button key="close" onClick={() => setItemModalId(null)}>关闭</Button>,
          <Button
            key="sync"
            type="primary"
            icon={<ReloadOutlined />}
            loading={itemModalId !== null && itemSyncingId === itemModalId}
            disabled={itemModalId === null}
            onClick={() => itemModalId !== null && handleSyncItems(itemModalId)}
          >
            同步商品
          </Button>,
        ]}
        width={900}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="这里展示的是闲鱼商品镜像摘要"
          description={`共 ${itemSummary.total} 个商品 · 已导入模板 ${itemSummary.imported} 个 · 未导入 ${itemSummary.unimported} 个。导入商品模板请到「设置 -> 商品模板 -> 从闲鱼导入商品」。`}
        />
        <Segmented
          size="small"
          value={itemTemplateFilter}
          onChange={(value) => setItemTemplateFilter(value as XianyuItemTemplateProjectionFilter)}
          options={[
            { label: '全部', value: 'all' },
            { label: '已导入模板', value: 'imported' },
            { label: '未导入模板', value: 'unimported' },
          ]}
          style={{ marginBottom: 12 }}
        />
        <Table
          rowKey="id"
          size="small"
          loading={itemLoading}
          dataSource={filteredItemMirrors}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无商品镜像，请先点击「同步商品」" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            {
              title: '商品',
              dataIndex: 'title',
              ellipsis: true,
              render: (v?: string, record?: any) => (
                <Space>
                  {record?.image_url && (
                    <img
                      src={record.image_url}
                      alt=""
                      style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }}
                    />
                  )}
                  <span>{v || '-'}</span>
                </Space>
              ),
            },
            {
              title: '状态',
              dataIndex: 'item_status',
              width: 100,
              render: (v?: string) => v ? <Tag>{v}</Tag> : '-',
            },
            {
              title: '模板',
              dataIndex: 'projected_template_id',
              width: 90,
              render: (v?: number) => v ? <Tag color="green">已导入</Tag> : <Tag>未导入</Tag>,
            },
            {
              title: '价格',
              dataIndex: 'price',
              width: 90,
              align: 'right' as const,
              render: (v: number) => `￥${Number(v || 0).toFixed(2)}`,
            },
            {
              title: '闲鱼商品ID',
              dataIndex: 'item_id',
              width: 150,
              render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
            },
            {
              title: '最近同步',
              dataIndex: 'last_seen_at',
              width: 150,
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
