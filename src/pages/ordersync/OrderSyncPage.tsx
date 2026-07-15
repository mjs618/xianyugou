import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Form, message, Result, Spin, Tag, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloudSyncOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import {
  listAccounts, createAccount, updateAccount, deleteAccount, testAccount,
  syncOrders, syncItems, checkBackend,
  formatSyncResultMessage, formatItemSyncResultMessage,
  hasSyncedOrdersToView, hasSyncedItemsToView,
  getCookieCloudConfigStatus, recoverAccount,
} from '@/services/xianyuService';
import { BACKEND_POLL_INTERVAL_MS } from '@/config/constants';
import { getErrorMessage, isValidationError } from '@/utils/error';
import type {
  XianyuAccount,
  CookieCloudConfigStatus,
  XianyuItemSyncResult,
  XianyuSyncResult,
} from '@/types';
import AccountCardGrid from './AccountCardGrid';
import AccountFormModal from './AccountFormModal';
import OrderMirrorModal from './OrderMirrorModal';
import ItemMirrorModal from './ItemMirrorModal';
import SyncLogModal from './SyncLogModal';
import OrderSyncOverview from './OrderSyncOverview';
import './orderSync.css';

const { Text } = Typography;

export default function OrderSyncPage() {
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
  const [orderModalId, setOrderModalId] = useState<number | null>(null);
  const [itemSyncingId, setItemSyncingId] = useState<number | null>(null);
  const [lastItemSyncResult, setLastItemSyncResult] = useState<XianyuItemSyncResult | null>(null);
  const [lastItemSyncAccountId, setLastItemSyncAccountId] = useState<number | null>(null);
  const [itemModalId, setItemModalId] = useState<number | null>(null);
  // P3：自动同步交互状态
  const [togglingId, setTogglingId] = useState<number | null>(null); // Switch loading
  const [recoveringId, setRecoveringId] = useState<number | null>(null); // 恢复按钮 loading
  const [editingInterval, setEditingInterval] = useState<Record<number, number>>({}); // 间隔输入中的值（未提交）
  const [form] = Form.useForm();

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await listAccounts();
      setAccounts(fresh);
      // 清除编辑中的间隔值，避免旧值覆盖新拉取的 API 数据
      // （loadAccounts 仅在挂载/创建/删除/同步/出错回滚时调用，此时用最新值最合理）
      setEditingInterval({});
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
    // 轮询后端状态（与 SendMail 一致，使用统一常量）
    const timer = setInterval(checkStatus, BACKEND_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadAccounts, checkStatus, loadCookieCloudStatus]);

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
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      message.error(getErrorMessage(err, '保存失败'));
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
        setItemModalId(id);
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '商品同步失败');
    } finally {
      setItemSyncingId(null);
    }
  };

  // P3：切换自动同步开关（乐观更新，避免 loadAccounts 闪烁）
  const handleToggleAutoSync = async (id: number, enabled: boolean) => {
    setTogglingId(id);
    // 乐观更新本地状态
    setAccounts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, auto_sync_enabled: enabled } : a))
    );
    try {
      await updateAccount(id, { auto_sync_enabled: enabled });
      message.success(enabled ? '已开启自动同步' : '已关闭自动同步');
    } catch (err) {
      // 回滚
      message.error(err instanceof Error ? err.message : '更新失败');
      loadAccounts();
    } finally {
      setTogglingId(null);
    }
  };

  // P3：提交自动同步间隔（onBlur / onPressEnter 时调用）
  const commitInterval = async (id: number) => {
    const pending = editingInterval[id];
    if (pending === undefined) return;
    const clamped = Math.max(60, Math.min(1440, pending));
    // 清除编辑中的值，切回已提交值
    setEditingInterval((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    // 乐观更新本地状态（不用 loadAccounts 避免 InputNumber 失焦）
    setAccounts((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, auto_sync_interval_minutes: clamped } : a
      )
    );
    try {
      await updateAccount(id, { auto_sync_interval_minutes: clamped });
      message.success(`同步间隔已设为 ${clamped} 分钟`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '更新失败');
      loadAccounts();
    }
  };

  // P3：从熔断暂停恢复（需先更新 Cookie）
  const handleRecover = async (id: number) => {
    setRecoveringId(id);
    try {
      const recovered = await recoverAccount(id);
      // 乐观更新本地状态
      setAccounts((prev) =>
        prev.map((a) => (a.id === id ? recovered : a))
      );
      const account = accounts.find((a) => a.id === id);
      if (account?.auto_sync_enabled) {
        message.success('账号已恢复，自动同步将在下个周期继续');
      } else {
        message.success('账号已恢复');
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    } finally {
      setRecoveringId(null);
    }
  };

  const handleEditAccount = (account: XianyuAccount) => {
    setEditing(account);
    form.setFieldsValue({ nickname: account.nickname });
    setModalOpen(true);
  };

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

  return (
    <Card
      title={<span><CloudSyncOutlined /> 订单同步</span>}
      extra={
        <>
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
        </>
      }
    >
      <OrderSyncOverview
        accounts={accounts}
        cookieCloudStatus={cookieCloudStatus}
        onReloadCookieCloud={loadCookieCloudStatus}
      />

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
                <Button size="small" onClick={() => setOrderModalId(lastSyncAccountId)}>
                  查看镜像订单
                </Button>
              )
              : undefined
          }
        />
      )}

      <AccountCardGrid
        accounts={accounts}
        loading={loading}
        syncingId={syncingId}
        onSync={handleSync}
        itemSyncingId={itemSyncingId}
        onSyncItems={handleSyncItems}
        onTest={handleTest}
        onOpenOrderMirror={(id) => setOrderModalId(id)}
        onOpenItemMirror={(id) => setItemModalId(id)}
        onOpenSyncLog={(id) => setLogModalId(id)}
        onEdit={handleEditAccount}
        onDelete={handleDelete}
        togglingId={togglingId}
        editingInterval={editingInterval}
        onToggleAutoSync={handleToggleAutoSync}
        onCommitInterval={commitInterval}
        onEditInterval={(id, value) => setEditingInterval((prev) => ({ ...prev, [id]: value }))}
        recoveringId={recoveringId}
        onRecover={handleRecover}
        onAddAccount={() => { setEditing(null); form.resetFields(); setModalOpen(true); }}
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
                <Button size="small" onClick={() => setItemModalId(lastItemSyncAccountId)}>
                  查看商品镜像
                </Button>
              )
              : undefined
          }
        />
      )}

      <AccountFormModal
        open={modalOpen}
        editing={editing}
        form={form}
        cookieCloudStatus={cookieCloudStatus}
        onCancel={() => { setModalOpen(false); setEditing(null); form.resetFields(); }}
        onOk={handleCreateOrUpdate}
      />

      <OrderMirrorModal
        accountId={orderModalId}
        onClose={() => setOrderModalId(null)}
      />

      <ItemMirrorModal
        accountId={itemModalId}
        syncing={itemSyncingId !== null && (itemModalId !== null ? itemSyncingId === itemModalId : false)}
        onSync={handleSyncItems}
        onClose={() => setItemModalId(null)}
      />

      <SyncLogModal
        accountId={logModalId}
        onClose={() => setLogModalId(null)}
      />
    </Card>
  );
}
