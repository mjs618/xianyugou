import type { ColumnsType } from 'antd/es/table';
import { Button, InputNumber, Popconfirm, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd';
import {
  ApiOutlined,
  CloudSyncOutlined,
  DeleteOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { XianyuAccount } from '@/types';

const { Text } = Typography;

// 账号状态标签
function StatusTag({ status }: { status: string }) {
  const map: Record<string, { text: string; color: string; icon: React.ReactNode }> = {
    online: { text: '在线', color: 'green', icon: <CheckCircleOutlined /> },
    invalid: { text: '失效', color: 'red', icon: <WarningOutlined /> },
    risk: { text: '风控', color: 'orange', icon: <WarningOutlined /> },
    paused: { text: '已熔断', color: 'volcano', icon: <SafetyCertificateOutlined /> },
  };
  const cfg = map[status] || { text: status, color: 'default', icon: <CheckCircleOutlined /> };
  return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>;
}

interface AccountTableProps {
  accounts: XianyuAccount[];
  loading: boolean;
  // 同步订单
  syncingId: number | null;
  onSync: (id: number) => void;
  // 同步商品
  itemSyncingId: number | null;
  onSyncItems: (id: number) => void;
  // 校验
  onTest: (id: number) => void;
  // 镜像/日志 Modal 打开
  onOpenOrderMirror: (id: number) => void;
  onOpenItemMirror: (id: number) => void;
  onOpenSyncLog: (id: number) => void;
  // 编辑/删除
  onEdit: (account: XianyuAccount) => void;
  onDelete: (id: number) => void;
  // 自动同步
  togglingId: number | null;
  editingInterval: Record<number, number>;
  onToggleAutoSync: (id: number, enabled: boolean) => void;
  onCommitInterval: (id: number) => void;
  onEditInterval: (id: number, value: number) => void;
  // 恢复
  recoveringId: number | null;
  onRecover: (id: number) => void;
}

/** 账号列表表格：展示账号信息 + 同步/校验/镜像/日志/编辑/删除操作 + 自动同步开关/间隔/恢复。
 *
 * 列定义从原 OrderSync 容器提取。StatusTag 也内联在此文件（仅本表格使用）。
 * 列 render 中调用的 handler 全部由容器通过 props 注入。
 */
export default function AccountTable({
  accounts,
  loading,
  syncingId,
  onSync,
  itemSyncingId,
  onSyncItems,
  onTest,
  onOpenOrderMirror,
  onOpenItemMirror,
  onOpenSyncLog,
  onEdit,
  onDelete,
  togglingId,
  editingInterval,
  onToggleAutoSync,
  onCommitInterval,
  onEditInterval,
  recoveringId,
  onRecover,
}: AccountTableProps) {
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
      title: '自动同步', dataIndex: 'auto_sync_enabled', width: 200,
      render: (enabled: boolean, r: XianyuAccount) => {
        const isPaused = r.status === 'paused';
        return (
          <Space size={4} direction="vertical" style={{ lineHeight: 1.2 }}>
            <Space size={4}>
              <Switch
                size="small"
                checked={enabled}
                loading={togglingId === r.id}
                disabled={isPaused}
                onChange={(checked) => onToggleAutoSync(r.id, checked)}
              />
              <Text style={{ fontSize: 12, color: enabled ? undefined : 'var(--color-text-tertiary)' }}>
                {enabled ? '已开启' : '关闭'}
              </Text>
            </Space>
            {enabled && (
              <Space size={2}>
                <Text style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>每</Text>
                <InputNumber
                  size="small"
                  style={{ width: 64 }}
                  min={60}
                  max={1440}
                  value={editingInterval[r.id] ?? r.auto_sync_interval_minutes}
                  disabled={isPaused}
                  onChange={(v) => {
                    if (v !== null) {
                      onEditInterval(r.id, v);
                    }
                  }}
                  onBlur={() => onCommitInterval(r.id)}
                  onPressEnter={() => onCommitInterval(r.id)}
                />
                <Text style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>分钟</Text>
              </Space>
            )}
            {enabled && r.consecutive_failures > 0 && (
              <Tooltip title={`连续失败 ${r.consecutive_failures} 次，达到 3 次将熔断`}>
                <Text style={{ fontSize: 11, color: 'var(--color-warning)' }}>
                  连续失败 {r.consecutive_failures}/3
                </Text>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: '最近错误', dataIndex: 'last_error', ellipsis: true,
      render: (v?: string) => v ? (
        <Tooltip title={v}><Text type="danger" style={{ fontSize: 12 }}>{v}</Text></Tooltip>
      ) : <Text style={{ color: 'var(--color-text-tertiary)' }}>-</Text>,
    },
    {
      title: '操作', width: 500, fixed: 'right',
      render: (_: unknown, r: XianyuAccount) => {
        const isPaused = r.status === 'paused';
        return (
          <Space size={4} wrap>
            <Button
              type="primary" size="small" icon={<SyncOutlined />}
              loading={syncingId === r.id}
              disabled={isPaused}
              onClick={() => onSync(r.id)}
            >同步订单</Button>
            {isPaused && (
              <Popconfirm
                title="恢复自动同步？"
                description="需先更新该账号的 Cookie（暂停后更新），通过校验后才能恢复。"
                onConfirm={() => onRecover(r.id)}
                disabled={recoveringId === r.id}
              >
                <Button
                  size="small"
                  type="primary"
                  ghost
                  icon={<SafetyCertificateOutlined />}
                  loading={recoveringId === r.id}
                >恢复</Button>
              </Popconfirm>
            )}
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={itemSyncingId === r.id}
              disabled={isPaused}
              onClick={() => onSyncItems(r.id)}
            >同步商品</Button>
            <Button size="small" icon={<ApiOutlined />} onClick={() => onTest(r.id)}>校验</Button>
            <Button size="small" icon={<CloudSyncOutlined />} onClick={() => onOpenOrderMirror(r.id)}>订单镜像</Button>
            <Button size="small" icon={<CloudSyncOutlined />} onClick={() => onOpenItemMirror(r.id)}>商品镜像</Button>
            <Button size="small" icon={<HistoryOutlined />} onClick={() => onOpenSyncLog(r.id)}>日志</Button>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => onEdit(r)} />
            <Popconfirm title="确认删除该账号？" onConfirm={() => onDelete(r.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <Table
      rowKey="id"
      size="middle"
      dataSource={accounts}
      columns={columns}
      loading={loading}
      pagination={false}
      scroll={{ x: 1280 }}
    />
  );
}
