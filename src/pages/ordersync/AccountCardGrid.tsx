import type { MenuProps } from 'antd';
import {
  Button,
  Card,
  Dropdown,
  Empty,
  InputNumber,
  Modal,
  Popconfirm,
  Skeleton,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  ApiOutlined,
  CheckCircleOutlined,
  CloudSyncOutlined,
  DeleteOutlined,
  EditOutlined,
  EllipsisOutlined,
  HistoryOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { XianyuAccount } from '@/types';

const { Text } = Typography;

interface AccountCardGridProps {
  accounts: XianyuAccount[];
  loading: boolean;
  syncingId: number | null;
  onSync: (id: number) => void;
  itemSyncingId: number | null;
  onSyncItems: (id: number) => void;
  onTest: (id: number) => void;
  onOpenOrderMirror: (id: number) => void;
  onOpenItemMirror: (id: number) => void;
  onOpenSyncLog: (id: number) => void;
  onEdit: (account: XianyuAccount) => void;
  onDelete: (id: number) => void;
  togglingId: number | null;
  editingInterval: Record<number, number>;
  onToggleAutoSync: (id: number, enabled: boolean) => void;
  onCommitInterval: (id: number) => void;
  onEditInterval: (id: number, value: number) => void;
  recoveringId: number | null;
  onRecover: (id: number) => void;
  onAddAccount: () => void;
}

const STATUS_MAP: Record<XianyuAccount['status'], {
  text: string;
  color: string;
  icon: React.ReactNode;
}> = {
  online: { text: '在线', color: 'green', icon: <CheckCircleOutlined /> },
  invalid: { text: '失效', color: 'red', icon: <WarningOutlined /> },
  risk: { text: '风控', color: 'orange', icon: <WarningOutlined /> },
  paused: { text: '已熔断', color: 'volcano', icon: <SafetyCertificateOutlined /> },
};

function StatusTag({ status }: { status: XianyuAccount['status'] }) {
  const config = STATUS_MAP[status];
  return <Tag color={config.color} icon={config.icon}>{config.text}</Tag>;
}

export default function AccountCardGrid({
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
  onAddAccount,
}: AccountCardGridProps) {
  if (loading) {
    return (
      <div className="order-sync-account-grid" aria-label="正在加载闲鱼账号">
        {[0, 1, 2].map((item) => (
          <Card key={item} className="order-sync-account-card"><Skeleton active paragraph={{ rows: 4 }} /></Card>
        ))}
      </div>
    );
  }

  if (accounts.length === 0) {
    return (
      <div className="order-sync-empty">
        <Empty description="还没有闲鱼账号">
          <Button
            aria-label="添加第一个账号"
            type="primary"
            icon={<PlusOutlined />}
            onClick={onAddAccount}
          >
            添加第一个账号
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div className="order-sync-account-grid" aria-label="闲鱼账号列表">
      {accounts.map((account) => {
        const isPaused = account.status === 'paused';
        const menuItems: MenuProps['items'] = [
          { key: 'test', icon: <ApiOutlined />, label: '校验 Cookie' },
          { key: 'orders', icon: <CloudSyncOutlined />, label: '订单镜像' },
          { key: 'items', icon: <CloudSyncOutlined />, label: '商品镜像' },
          { key: 'logs', icon: <HistoryOutlined />, label: '同步日志' },
          ...(!isPaused ? [{ key: 'edit', icon: <EditOutlined />, label: '编辑账号' }] : []),
          { type: 'divider' as const },
          { key: 'delete', icon: <DeleteOutlined />, label: '删除账号', danger: true },
        ];

        const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
          if (key === 'test') onTest(account.id);
          if (key === 'orders') onOpenOrderMirror(account.id);
          if (key === 'items') onOpenItemMirror(account.id);
          if (key === 'logs') onOpenSyncLog(account.id);
          if (key === 'edit') onEdit(account);
          if (key === 'delete') {
            Modal.confirm({
              title: `删除账号「${account.nickname}」？`,
              content: '删除后该账号将不再同步，已有交易记录不会被删除。',
              okText: '删除',
              okButtonProps: { danger: true },
              cancelText: '取消',
              onOk: () => onDelete(account.id),
            });
          }
        };

        return (
          <article key={account.id} aria-labelledby={`order-sync-account-${account.id}`}>
            <Card className={`order-sync-account-card${isPaused ? ' order-sync-account-card--paused' : ''}`}>
              <div className="order-sync-account-header">
                <div>
                  <div className="order-sync-account-title-row">
                    <h2 id={`order-sync-account-${account.id}`}>{account.nickname}</h2>
                    <StatusTag status={account.status} />
                  </div>
                  <Text type="secondary" className="order-sync-account-id">
                    {account.unb ? `账号 ID ${account.unb}` : '尚未获取账号 ID'}
                  </Text>
                </div>
                <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
                  <Button
                    aria-label={`更多操作 ${account.nickname}`}
                    icon={<EllipsisOutlined />}
                    size="small"
                  >
                    更多
                  </Button>
                </Dropdown>
              </div>

              <div className="order-sync-account-stats">
                <div>
                  <span>上次同步</span>
                  <strong>{account.last_sync_at ? dayjs(account.last_sync_at).format('MM-DD HH:mm') : '从未同步'}</strong>
                </div>
                <div>
                  <span>自动同步</span>
                  <Space size={6}>
                    <Switch
                      aria-label={`自动同步 ${account.nickname}`}
                      size="small"
                      checked={account.auto_sync_enabled}
                      loading={togglingId === account.id}
                      disabled={isPaused}
                      onChange={(checked) => onToggleAutoSync(account.id, checked)}
                    />
                    <strong>{account.auto_sync_enabled ? '已开启' : '已关闭'}</strong>
                  </Space>
                </div>
              </div>

              {account.auto_sync_enabled && (
                <div className="order-sync-interval-row">
                  <span>每</span>
                  <InputNumber
                    aria-label={`自动同步间隔 ${account.nickname}`}
                    size="small"
                    min={60}
                    max={1440}
                    value={editingInterval[account.id] ?? account.auto_sync_interval_minutes}
                    disabled={isPaused}
                    onChange={(value) => {
                      if (value !== null) onEditInterval(account.id, value);
                    }}
                    onBlur={() => onCommitInterval(account.id)}
                    onPressEnter={() => onCommitInterval(account.id)}
                  />
                  <span>分钟同步一次</span>
                  {account.consecutive_failures > 0 && (
                    <Tooltip title="连续失败达到 3 次将熔断">
                      <Text type="warning">失败 {account.consecutive_failures}/3</Text>
                    </Tooltip>
                  )}
                </div>
              )}

              {account.last_error && (
                <div className="order-sync-account-error" role="status">
                  <WarningOutlined />
                  <span><strong>最近错误</strong>{account.last_error}</span>
                </div>
              )}

              <div className="order-sync-account-actions">
                {isPaused ? (
                  <>
                    <Button
                      aria-label={`更新 Cookie ${account.nickname}`}
                      type="primary"
                      icon={<EditOutlined />}
                      onClick={() => onEdit(account)}
                    >
                      更新 Cookie
                    </Button>
                    <Popconfirm
                      title="校验并恢复账号？"
                      description="请确认已更新 Cookie；系统会先执行只读校验，通过后解除暂停。"
                      onConfirm={() => onRecover(account.id)}
                      disabled={recoveringId === account.id}
                    >
                      <Button
                        aria-label={`校验并恢复 ${account.nickname}`}
                        danger
                        icon={<SafetyCertificateOutlined />}
                        loading={recoveringId === account.id}
                      >
                        校验并恢复
                      </Button>
                    </Popconfirm>
                  </>
                ) : (
                  <>
                    <Button
                      aria-label={`同步订单 ${account.nickname}`}
                      type="primary"
                      icon={<SyncOutlined />}
                      loading={syncingId === account.id}
                      onClick={() => onSync(account.id)}
                    >
                      同步订单
                    </Button>
                    <Button
                      aria-label={`同步商品 ${account.nickname}`}
                      icon={<ReloadOutlined />}
                      loading={itemSyncingId === account.id}
                      onClick={() => onSyncItems(account.id)}
                    >
                      同步商品
                    </Button>
                  </>
                )}
              </div>
            </Card>
          </article>
        );
      })}
    </div>
  );
}
