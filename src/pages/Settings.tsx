import { useEffect, useRef, useState } from 'react';
import { Card, Tabs, Form, InputNumber, Input, Button, Select, Table, Space, message, Popconfirm, Modal, Row, Col, Switch, Tag, Alert, Descriptions, Skeleton, Empty, Typography, Upload, Segmented } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, DownloadOutlined, UploadOutlined, DatabaseOutlined, ExperimentOutlined, BellOutlined, CheckOutlined, BgColorsOutlined, MailOutlined, AppstoreOutlined, SettingOutlined, HistoryOutlined, SafetyOutlined, ReloadOutlined, FileExcelOutlined, FileTextOutlined, UndoOutlined, CloudDownloadOutlined, CloudUploadOutlined } from '@ant-design/icons';
import { listTemplates, createTemplate, updateTemplate, deleteTemplate } from '@/services/productTemplateService';
import { getSettings, updateSettings } from '@/services/settingsService';
import { getFinanceOverview, getProductProfitStats, getCustomerValueStats } from '@/services/financeService';
import { listTransactions } from '@/services/transactionService';
import { listCustomers } from '@/services/customerService';
import { listRebates } from '@/services/rebateService';
import { exportJSON, importJSON, downloadFile, downloadBlob, exportTransactionsCSV, exportCustomersCSV, exportFinanceReportExcel } from '@/utils/export';
import { seedDemoData, hasData } from '@/utils/seed';
import { requestNotificationPermission, getNotificationPermission, runAllReminderChecks } from '@/services/notificationService';
import { listLogs, clearLogs, getLogCount } from '@/services/auditLogService';
import {
  filterXianyuItemsByTemplateProjection,
  importXianyuItemsAsTemplates,
  listAccounts as listXianyuAccounts,
  listItems as listXianyuItems,
  syncItems as syncXianyuItems,
} from '@/services/xianyuService';
import type { XianyuItemTemplateProjectionFilter } from '@/services/xianyuService';
import { isEncryptedBackup } from '@/utils/crypto';
import { getWarrantyDaysLabel } from '@/utils/warranty';
import {
  listTrashedCustomers,
  listTrashedTransactions,
  listTrashedAfterSales,
  restoreCustomer,
  restoreTransaction,
  restoreAfterSales,
  purgeCustomer,
  purgeTransaction,
  purgeAfterSales,
  SOFT_DELETE_RETENTION_DAYS,
} from '@/services/trashService';
import { useAppStore } from '@/store/useAppStore';
import { useThemeStore } from '@/store/useThemeStore';
import { themes } from '@/config/themes';
import dayjs from 'dayjs';
import type { ProductTemplate, Settings, OperationLog, AuditModule, Customer, Transaction, AfterSales, XianyuAccount, XianyuItem } from '@/types';

const { Text } = Typography;

function displayImageUrl(url?: string): string | undefined {
  if (!url) return undefined;
  let normalized = url.startsWith('//') ? `https:${url}` : url;
  normalized = normalized.replace(/^http:\/\/img\.alicdn\.com\//, 'https://img.alicdn.com/');
  if (/\.(heic|heif)(?:$|\?)/i.test(normalized) && !/_\d+x\d+\.jpg(?:$|\?)/i.test(normalized)) {
    normalized = normalized.split('?')[0] + '_120x120.jpg';
  }
  return normalized;
}

function ProductTemplateImage({ url }: { url?: string }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [url]);

  const src = displayImageUrl(url);
  if (!src || failed) {
    return <Text style={{ color: 'var(--color-text-tertiary)' }}>无图</Text>;
  }

  return (
    <img
      src={src}
      alt=""
      onError={() => setFailed(true)}
      style={{ width: 44, height: 44, objectFit: 'cover', borderRadius: 6, background: '#f5f5f5' }}
    />
  );
}

export default function SettingsPage() {
  const { refreshAll } = useAppStore();
  const { themeId, setTheme } = useThemeStore();
  const [activeTab, setActiveTab] = useState('theme');
  const [templates, setTemplates] = useState<ProductTemplate[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [tplModalOpen, setTplModalOpen] = useState(false);
  const [editingTpl, setEditingTpl] = useState<ProductTemplate | null>(null);
  const [xianyuImportOpen, setXianyuImportOpen] = useState(false);
  const [xianyuAccounts, setXianyuAccounts] = useState<XianyuAccount[]>([]);
  const [templateSourceFilter, setTemplateSourceFilter] = useState<string | number>('all');
  const [xianyuImportAccountId, setXianyuImportAccountId] = useState<number | undefined>(undefined);
  const [xianyuItems, setXianyuItems] = useState<XianyuItem[]>([]);
  const [xianyuItemImportFilter, setXianyuItemImportFilter] = useState<XianyuItemTemplateProjectionFilter>('unimported');
  const [selectedXianyuItemIds, setSelectedXianyuItemIds] = useState<number[]>([]);
  const [xianyuItemsLoading, setXianyuItemsLoading] = useState(false);
  const [xianyuImporting, setXianyuImporting] = useState(false);
  const [xianyuImportDefaultCost, setXianyuImportDefaultCost] = useState(0);
  const [xianyuImportWarrantyDays, setXianyuImportWarrantyDays] = useState(30);
  const [tplForm] = Form.useForm();
  const [settingsForm] = Form.useForm();
  const [mailForm] = Form.useForm();
  const [notifPermission, setNotifPermission] = useState(getNotificationPermission());
  const [hasExistingData, setHasExistingData] = useState(false);
  const [auditLogs, setAuditLogs] = useState<OperationLog[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditModuleFilter, setAuditModuleFilter] = useState<AuditModule | undefined>(undefined);
  const [auditPage, setAuditPage] = useState(1);
  // P0-2 备份加密：导出/导入时可选密码
  const [exportPassword, setExportPassword] = useState('');
  const [importFileContent, setImportFileContent] = useState<string | null>(null);
  // P1 修复：Modal.confirm 是非受控渲染，弹窗内的输入框 value 不会随 state 更新；
  // 用 ref 在 onChange 时同步最新值，确保 onOk 时读到的是用户实际输入的密码
  const importPasswordRef = useRef('');
  // P0-1 回收站：列出已软删除的数据
  const [trashedCustomers, setTrashedCustomers] = useState<Customer[]>([]);
  const [trashedTransactions, setTrashedTransactions] = useState<Transaction[]>([]);
  const [trashedAfterSales, setTrashedAfterSales] = useState<AfterSales[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);
  const loadTemplates = async () => {
    setTemplates(await listTemplates());
  };

  const loadXianyuAccountOptions = async () => {
    try {
      setXianyuAccounts(await listXianyuAccounts());
    } catch {
      // 设置页仍可管理普通模板；账号信息只用于闲鱼来源展示和筛选。
    }
  };

  const loadSettings = async () => {
    const s = await getSettings();
    setSettings(s);
    settingsForm.setFieldsValue(s);
    mailForm.setFieldsValue(s);
  };

  useEffect(() => {
    Promise.all([
      loadTemplates(),
      loadSettings(),
      loadXianyuAccountOptions(),
      hasData().then(setHasExistingData),
    ]).finally(() => setLoading(false));
  }, []);

  const loadAuditLogs = async (page = auditPage, module = auditModuleFilter) => {
    const limit = 50;
    const offset = (page - 1) * limit;
    const [logs, total] = await Promise.all([
      listLogs({ module, limit, offset }),
      getLogCount(module),
    ]);
    setAuditLogs(logs);
    setAuditTotal(total);
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs(1);
    }
  }, [activeTab, auditModuleFilter]);

  // P0-1 回收站加载
  const loadTrash = async () => {
    setTrashLoading(true);
    try {
      const [c, t, a] = await Promise.all([
        listTrashedCustomers(),
        listTrashedTransactions(),
        listTrashedAfterSales(),
      ]);
      setTrashedCustomers(c);
      setTrashedTransactions(t);
      setTrashedAfterSales(a);
    } catch (err) {
      console.error('加载回收站失败:', err);
      message.error('加载回收站失败');
    } finally {
      setTrashLoading(false);
    }
  };

  const openXianyuImport = async () => {
    setXianyuImportOpen(true);
    setSelectedXianyuItemIds([]);
    setXianyuItemImportFilter('unimported');
    setXianyuImportDefaultCost(0);
    setXianyuImportWarrantyDays(settings?.warranty_days ?? 30);
    setXianyuItems([]);
    try {
      const accounts = await listXianyuAccounts();
      setXianyuAccounts(accounts);
      const firstId = accounts[0]?.id;
      setXianyuImportAccountId(firstId);
      if (firstId) {
        setXianyuItemsLoading(true);
        setXianyuItems(await listXianyuItems(firstId));
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载闲鱼账号失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const loadXianyuItems = async (accountId = xianyuImportAccountId) => {
    if (!accountId) return;
    setXianyuItemsLoading(true);
    setSelectedXianyuItemIds([]);
    try {
      setXianyuItems(await listXianyuItems(accountId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载闲鱼商品失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const handleSyncXianyuItems = async () => {
    if (!xianyuImportAccountId) {
      message.warning('请先选择闲鱼账号');
      return;
    }
    setXianyuItemsLoading(true);
    setSelectedXianyuItemIds([]);
    try {
      const result = await syncXianyuItems(xianyuImportAccountId);
      if (result.success) {
        message.success(`拉取完成：拉取 ${result.fetched} 个商品，更新 ${result.upserted_count} 个镜像`);
      } else {
        message.warning(`拉取未完成：${result.error || '未知原因'}`);
      }
      setXianyuItems(await listXianyuItems(xianyuImportAccountId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : '拉取闲鱼商品失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const handleImportXianyuItems = async () => {
    if (!xianyuImportAccountId || selectedXianyuItemIds.length === 0) {
      message.warning('请先选择要导入的商品');
      return;
    }
    if (xianyuImportDefaultCost < 0 || xianyuImportWarrantyDays < 0) {
      message.warning('请填写有效的默认成本和质保天数');
      return;
    }
    setXianyuImporting(true);
    try {
      const result = await importXianyuItemsAsTemplates(
        xianyuImportAccountId,
        selectedXianyuItemIds,
        {
          default_cost: xianyuImportDefaultCost,
          warranty_days: xianyuImportWarrantyDays,
        },
      );
      message.success(`导入完成：新增 ${result.created_count} 个模板，跳过 ${result.skipped_count} 个`);
      setSelectedXianyuItemIds([]);
      await Promise.all([loadTemplates(), loadXianyuItems(xianyuImportAccountId)]);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导入商品模板失败');
    } finally {
      setXianyuImporting(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'trash') {
      loadTrash();
    }
  }, [activeTab]);

  // P0-1 恢复操作
  const handleRestoreCustomer = async (id: number) => {
    try {
      await restoreCustomer(id);
      message.success('客户已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  const handleRestoreTransaction = async (id: number) => {
    try {
      await restoreTransaction(id);
      message.success('交易已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  const handleRestoreAfterSales = async (id: number) => {
    try {
      await restoreAfterSales(id);
      message.success('工单已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  // P0-1 彻底删除
  const handlePurgeCustomer = async (id: number) => {
    try {
      await purgeCustomer(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };
  const handlePurgeTransaction = async (id: number) => {
    try {
      await purgeTransaction(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };
  const handlePurgeAfterSales = async (id: number) => {
    try {
      await purgeAfterSales(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleSaveTpl = async () => {
    try {
      const values = await tplForm.validateFields();
      if (editingTpl) {
        await updateTemplate(editingTpl.id!, values);
        message.success('模板已更新');
      } else {
        await createTemplate(values);
        message.success('模板已创建');
      }
      setTplModalOpen(false);
      setEditingTpl(null);
      tplForm.resetFields();
      loadTemplates();
    } catch (err: any) {
      if (err?.errorFields) return;
      console.error('保存模板失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleDeleteTpl = async (id: number) => {
    try {
      await deleteTemplate(id);
      message.success('已删除');
      loadTemplates();
    } catch (err) {
      console.error('删除模板失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleSaveSettings = async () => {
    try {
      const values = await settingsForm.validateFields();
      await updateSettings(values);
      message.success('设置已保存');
      refreshAll();
      loadSettings();
    } catch (err: any) {
      if (err?.errorFields) return;
      console.error('保存设置失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleSaveMail = async () => {
    try {
      const values = await mailForm.validateFields();
      await updateSettings(values);
      message.success('邮件配置已保存');
      loadSettings();
    } catch (err: any) {
      if (err?.errorFields) return;
      console.error('保存邮件配置失败:', err);
      message.error(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleExport = async () => {
    try {
      const pwd = exportPassword.trim() || undefined;
      const json = await exportJSON(pwd);
      const suffix = pwd ? '_加密' : '';
      downloadFile(json, `闲鱼记账备份${suffix}_${dayjs().format('YYYYMMDD_HHmmss')}.json`, 'application/json');
      message.success(pwd ? '已导出加密备份' : '备份已导出');
      // 导出后清空密码输入，避免泄露
      setExportPassword('');
    } catch (err) {
      console.error('导出备份失败:', err);
      message.error(err instanceof Error ? err.message : '导出失败');
    }
  };

  // P0-2：先读取文件内容，检测是否加密，加密则要求输入密码
  const handleImportFileSelect = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      const isEnc = isEncryptedBackup(content.trim());
      setImportFileContent(content);
      // P1 修复：同时重置 ref，避免上次的密码残留
      importPasswordRef.current = '';
      Modal.confirm({
        title: '确认恢复数据',
        content: (
          <div>
            <p>恢复操作将覆盖当前所有数据，且不可撤销。确定要继续吗？</p>
            {isEnc && (
              <div style={{ marginTop: 8 }}>
                <p style={{ color: 'var(--color-warning)' }}>该备份已加密，请输入密码：</p>
                {/* 非受控输入：Modal.confirm 不会随 state 重渲染，使用 ref 持有最新值 */}
                <Input.Password
                  placeholder="备份密码"
                  onChange={(ev) => {
                    importPasswordRef.current = ev.target.value;
                  }}
                  autoFocus
                />
              </div>
            )}
            {!isEnc && <p style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>该备份未加密。</p>}
          </div>
        ),
        okText: '确认恢复',
        okType: 'danger',
        cancelText: '取消',
        onOk: () => handleImportConfirm(),
      });
    };
    reader.onerror = () => {
      message.error('文件读取失败');
    };
    reader.readAsText(file);
    return false;
  };

  const handleImportConfirm = async () => {
    if (!importFileContent) {
      message.error('未读取到备份内容');
      return;
    }
    try {
      // P1 修复：从 ref 读取最新输入的密码，避免闭包读到旧值
      const pwd = importPasswordRef.current.trim() || undefined;
      await importJSON(importFileContent, pwd);
      message.success('备份已恢复');
      refreshAll();
      loadTemplates();
      loadSettings();
      setHasExistingData(await hasData());
      // 清空状态
      setImportFileContent(null);
      importPasswordRef.current = '';
    } catch (err: any) {
      message.error('恢复失败：' + (err.message || '文件格式错误'));
    }
  };

  const handleSeed = async () => {
    try {
      await seedDemoData();
      message.success('演示数据已生成');
      refreshAll();
      setHasExistingData(await hasData());
    } catch (err) {
      console.error('生成演示数据失败:', err);
      message.error(err instanceof Error ? err.message : '生成失败');
    }
  };

  // CSV/Excel 数据导出（P3-1：在设置页提供统一入口，便于一次性导出全量数据）
  const [csvExporting, setCsvExporting] = useState(false);

  const handleExportAllTransactionsCSV = async () => {
    setCsvExporting(true);
    try {
      const all = await listTransactions();
      const csv = exportTransactionsCSV(all);
      downloadFile(csv, `全部交易明细_${dayjs().format('YYYYMMDD')}.csv`, 'text/csv');
      message.success(`已导出 ${all.length} 条交易`);
    } catch (err) {
      console.error('导出交易明细 CSV 失败:', err);
      message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setCsvExporting(false);
    }
  };

  const handleExportAllCustomersCSV = async () => {
    setCsvExporting(true);
    try {
      const all = await listCustomers();
      const csv = exportCustomersCSV(all);
      downloadFile(csv, `全部客户明细_${dayjs().format('YYYYMMDD')}.csv`, 'text/csv');
      message.success(`已导出 ${all.length} 条客户`);
    } catch (err) {
      console.error('导出客户明细 CSV 失败:', err);
      message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setCsvExporting(false);
    }
  };

  // 全量财务报表 Excel（含 5 个 Sheet：收支总览/交易明细/商品排行/客户排行/返利记录）
  // 覆盖全部历史数据，与 FinanceReport 页按周期过滤不同
  const handleExportFullExcel = async () => {
    setCsvExporting(true);
    try {
      const [overview, transactions, products, customers, rebates] = await Promise.all([
        getFinanceOverview(),
        listTransactions(),
        getProductProfitStats(),
        getCustomerValueStats(100),
        listRebates(),
      ]);
      const blob = await exportFinanceReportExcel({
        overview,
        rangeStart: transactions.length > 0
          ? transactions.reduce((min, t) => (t.trade_at < min ? t.trade_at : min), transactions[0].trade_at)
          : dayjs().startOf('year').toDate(),
        rangeEnd: new Date(),
        transactions,
        products,
        customers,
        rebates,
      });
      downloadBlob(blob, `财务报表_全量_${dayjs().format('YYYYMMDDHHmm')}.xlsx`);
      message.success(`已导出 Excel（含 ${transactions.length} 条交易 / ${rebates.length} 条返利）`);
    } catch (err) {
      console.error('导出 Excel 失败:', err);
      message.error(err instanceof Error ? err.message : '导出失败');
    } finally {
      setCsvExporting(false);
    }
  };

  const handleEnableNotification = async () => {
    try {
      const granted = await requestNotificationPermission();
      setNotifPermission(getNotificationPermission());
      if (granted) {
        message.success('通知已开启，将为您推送提醒');
        await runAllReminderChecks();
        refreshAll();
      } else {
        message.warning('通知权限未开启，请在浏览器设置中允许通知');
      }
    } catch (err) {
      console.error('开启通知失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleTestNotification = () => {
    if (notifPermission === 'granted') {
      try {
        new Notification('测试通知', { body: '闲鱼记账助手通知功能正常工作！' });
        message.success('测试通知已发送');
      } catch {
        message.error('通知发送失败');
      }
    } else {
      message.warning('请先开启通知权限');
    }
  };

  const handleClearLogs = async () => {
    await clearLogs();
    message.success('操作日志已清空');
    loadAuditLogs(1);
  };

  const xianyuAccountNameById = new Map(
    xianyuAccounts.map((account) => [account.id, account.nickname || account.unb || `账号 ${account.id}`]),
  );

  const tplColumns = [
    {
      title: '图片',
      dataIndex: 'image_url',
      width: 70,
      render: (v?: string) => <ProductTemplateImage url={v} />,
    },
    { title: '商品名称', dataIndex: 'name', ellipsis: true },
    { title: '默认成本', dataIndex: 'default_cost', width: 100, render: (v: number) => `¥${v}` },
    { title: '建议售价', dataIndex: 'default_sale_price', width: 100, render: (v?: number) => (v ? `¥${v}` : '-') },
    { title: '分类', dataIndex: 'category', width: 100, render: (v?: string) => v || '-' },
    {
      title: '来源账号',
      dataIndex: 'source_xianyu_account_id',
      width: 130,
      filters: xianyuAccounts.map((account) => ({
        text: account.nickname || account.unb || `账号 ${account.id}`,
        value: account.id,
      })),
      onFilter: (value: any, record: ProductTemplate) => record.source_xianyu_account_id === Number(value),
      render: (v?: number) => {
        if (!v) return <Tag>手动</Tag>;
        return <Tag color="blue">{xianyuAccountNameById.get(v) || `账号 ${v}`}</Tag>;
      },
    },
    { title: '质保天数', dataIndex: 'warranty_days', width: 90, align: 'center' as const, render: (v: number) => getWarrantyDaysLabel(v) },
    {
      title: '启用',
      dataIndex: 'is_active',
      width: 70,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    {
      title: '操作',
      width: 120,
      render: (_: unknown, r: ProductTemplate) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingTpl(r); tplForm.setFieldsValue(r); setTplModalOpen(true); }} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDeleteTpl(r.id!)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const xianyuItemColumns = [
    { title: '商品', dataIndex: 'title', ellipsis: true, render: (v?: string) => v || '-' },
    { title: '售价', dataIndex: 'price', width: 90, align: 'right' as const, render: (v: number) => `¥${Number(v || 0).toFixed(2)}` },
    { title: '状态', dataIndex: 'item_status', width: 100, render: (v?: string) => v ? <Tag>{v}</Tag> : '-' },
    {
      title: '导入',
      dataIndex: 'projected_template_id',
      width: 100,
      render: (v?: number) => v ? <Tag color="green">已导入</Tag> : <Tag>未导入</Tag>,
    },
    { title: '闲鱼商品ID', dataIndex: 'item_id', width: 150, render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text> },
    {
      title: '最近拉取',
      dataIndex: 'last_seen_at',
      width: 150,
      render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ];

  if (loading) {
    return (
      <Card title="系统设置">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    );
  }

  const emptyText = <Empty description="暂无模板" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  const filteredXianyuItems = filterXianyuItemsByTemplateProjection(xianyuItems, xianyuItemImportFilter);
  const filteredTemplates = templates.filter((tpl) => {
    if (templateSourceFilter === 'all') return true;
    if (templateSourceFilter === 'manual') return !tpl.source_xianyu_account_id;
    return tpl.source_xianyu_account_id === Number(templateSourceFilter);
  });
  const importedTemplateCount = templates.filter((tpl) => Boolean(tpl.source_xianyu_account_id)).length;

  return (
    <Card title="系统设置">
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'theme',
            label: <span><BgColorsOutlined /> 主题</span>,
            children: (
              <div>
                <p style={{ color: 'var(--color-text-secondary)', marginBottom: 24 }}>选择应用的主题色彩方案，切换后立即生效</p>
                <Row gutter={[16, 16]}>
                  {themes.map((t) => (
                    <Col key={t.id} xs={12} sm={8} md={6}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => {
                          setTheme(t.id);
                          message.success(`已切换到「${t.name}」主题`);
                        }}
                        style={{
                          cursor: 'pointer',
                          border: themeId === t.id ? `1px solid ${t.swatch}` : '1px solid var(--color-border)',
                          transition: 'border-color 0.2s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: 6,
                              background: t.swatch,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#fff',
                            }}
                          >
                            {themeId === t.id && <CheckOutlined style={{ fontSize: 16 }} />}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--color-dark)', fontSize: 13 }}>{t.name}</div>
                            <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                              <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primary }} />
                              <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primaryLight }} />
                              <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primaryBorder }} />
                            </div>
                          </div>
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>
                <Alert
                  type="info"
                  message="主题偏好已自动保存到本地，下次打开应用时自动恢复"
                  style={{ marginTop: 24 }}
                  showIcon
                />
              </div>
            ),
          },
          {
            key: 'templates',
            label: <span><AppstoreOutlined /> 商品模板</span>,
            children: (
              <>
                <Space style={{ marginBottom: 16 }} wrap>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => {
                      setEditingTpl(null);
                      tplForm.resetFields();
                      tplForm.setFieldsValue({ is_active: true, warranty_days: settings?.warranty_days ?? 30 });
                      setTplModalOpen(true);
                    }}
                  >
                    新增模板
                  </Button>
                  <Button icon={<CloudDownloadOutlined />} onClick={openXianyuImport}>
                    从闲鱼导入
                  </Button>
                  <Select
                    style={{ width: 220 }}
                    value={templateSourceFilter}
                    onChange={setTemplateSourceFilter}
                    options={[
                      { label: `全部模板（${templates.length}）`, value: 'all' },
                      { label: `手动模板（${templates.length - importedTemplateCount}）`, value: 'manual' },
                      ...xianyuAccounts.map((account) => ({
                        label: `${account.nickname || account.unb || `账号 ${account.id}`}（${templates.filter((tpl) => tpl.source_xianyu_account_id === account.id).length}）`,
                        value: account.id,
                      })),
                    ]}
                  />
                </Space>
                <Table
                  rowKey="id"
                  dataSource={filteredTemplates}
                  columns={tplColumns}
                  size="middle"
                  pagination={{ pageSize: 20 }}
                  locale={{ emptyText }}
                  scroll={{ x: 980 }}
                />
              </>
            ),
          },
          {
            key: 'system',
            label: <span><SettingOutlined /> 系统设置</span>,
            children: (
              <Form form={settingsForm} layout="vertical" style={{ maxWidth: 600 }}>
                <Form.Item name="warranty_days" label="默认质保周期（天）" tooltip="填 0 表示新订单默认不质保" rules={[{ required: true }]}>
                  <InputNumber min={0} max={3650} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item name="rebate_rate" label="返利比例（0-1，如0.1表示10%）" rules={[{ required: true }]}>
                  <InputNumber min={0} max={1} step={0.01} precision={2} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item name="rebate_base" label="返利基数" rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'profit', label: '利润（默认）' },
                      { value: 'sale', label: '售价' },
                    ]}
                  />
                </Form.Item>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item name="vip_threshold" label="VIP 金额阈值（元）" rules={[{ required: true }]}>
                      <InputNumber min={0} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="vip_trade_count" label="VIP 笔数阈值" rules={[{ required: true }]}>
                      <InputNumber min={1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item name="core_threshold" label="核心客户金额阈值（元）" rules={[{ required: true }]}>
                      <InputNumber min={0} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name="core_trade_count" label="核心客户笔数阈值" rules={[{ required: true }]}>
                      <InputNumber min={1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item name="recall_days" label="客户回访提醒间隔（天）" rules={[{ required: true }]}>
                  <InputNumber min={1} max={365} style={{ width: '100%' }} />
                </Form.Item>
                <Button type="primary" onClick={handleSaveSettings}>保存设置</Button>
              </Form>
            ),
          },
          {
            key: 'mail',
            label: <span><MailOutlined /> 邮件配置</span>,
            children: (
              <Form form={mailForm} layout="vertical" style={{ maxWidth: 600 }}>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="QQ 邮箱 SMTP 配置"
                  description={
                    <span>
                      需在 QQ 邮箱「设置 - 账户」中开启 SMTP 服务并获取授权码（授权码不是邮箱登录密码）。
                      配置完成后，请运行 <Text code>npm run mail-server</Text> 启动邮件服务，即可在「发货邮件」页面一键发送。
                    </span>
                  }
                />
                <Row gutter={16}>
                  <Col span={14}>
                    <Form.Item name="smtp_host" label="SMTP 服务器" rules={[{ required: true }]}>
                      <Input placeholder="smtp.qq.com" />
                    </Form.Item>
                  </Col>
                  <Col span={10}>
                    <Form.Item name="smtp_port" label="SMTP 端口" rules={[{ required: true }]}>
                      <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item name="smtp_user" label="发件邮箱（QQ 邮箱地址）" rules={[{ required: true }]}>
                  <Input placeholder="如：123456@qq.com" />
                </Form.Item>
                <Form.Item name="smtp_pass" label="SMTP 授权码" rules={[{ required: true }]}>
                  <Input.Password placeholder="QQ 邮箱 SMTP 授权码" />
                </Form.Item>
                <Form.Item name="smtp_from" label="发件人显示（选填）" tooltip="如不填，默认使用发件邮箱地址">
                  <Input placeholder="如：闲鱼助手 <123456@qq.com>" />
                </Form.Item>
                <Button type="primary" onClick={handleSaveMail}>保存邮件配置</Button>
              </Form>
            ),
          },
          {
            key: 'notification',
            label: <span><BellOutlined /> 通知设置</span>,
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Card type="inner" title={<span><BellOutlined /> 浏览器通知</span>}>
                  <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
                    <Descriptions.Item label="当前状态">
                      {notifPermission === 'granted' ? (
                        <Tag color="green">已开启</Tag>
                      ) : notifPermission === 'denied' ? (
                        <Tag color="red">已拒绝</Tag>
                      ) : notifPermission === 'unsupported' ? (
                        <Tag color="default">不支持</Tag>
                      ) : (
                        <Tag color="orange">未开启</Tag>
                      )}
                    </Descriptions.Item>
                  </Descriptions>
                  {notifPermission === 'denied' && (
                    <Alert
                      type="warning"
                      message="通知权限已被拒绝"
                      description={'请在浏览器地址栏点击锁图标，将通知权限改为"允许"，然后刷新页面。'}
                      style={{ marginBottom: 16 }}
                    />
                  )}
                  <Space>
                    {notifPermission !== 'granted' && notifPermission !== 'denied' && notifPermission !== 'unsupported' && (
                      <Button type="primary" icon={<BellOutlined />} onClick={handleEnableNotification}>
                        开启通知
                      </Button>
                    )}
                    {notifPermission === 'granted' && (
                      <Button icon={<BellOutlined />} onClick={handleTestNotification}>
                        发送测试通知
                      </Button>
                    )}
                  </Space>
                </Card>
                <Card type="inner" title="提醒类型说明">
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="质保到期提醒">
                      质保到期前 3 天自动推送提醒（应用内通知 + 浏览器通知）
                    </Descriptions.Item>
                    <Descriptions.Item label="客户回访提醒">
                      VIP/核心客户超过设定天数未交易时，自动推送回访提醒
                    </Descriptions.Item>
                    <Descriptions.Item label="返利结算提醒">
                      有待结算返利时，每日推送提醒
                    </Descriptions.Item>
                  </Descriptions>
                  <p style={{ color: 'var(--color-text-secondary)', fontSize: 12, marginTop: 12 }}>
                    提醒检查在应用启动时和每 10 分钟自动执行一次。
                  </p>
                </Card>
              </Space>
            ),
          },
          {
            key: 'backup',
            label: <span><DatabaseOutlined /> 数据备份与恢复</span>,
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Card type="inner" title={<span><DatabaseOutlined /> 数据备份</span>}>
                  <p style={{ color: 'var(--color-text-secondary)' }}>导出全部数据为 JSON 文件，可用于跨设备迁移或数据备份。</p>
                  <div style={{ marginBottom: 12 }}>
                    <Input.Password
                      placeholder="可选：为备份设置密码（留空则不加密）"
                      value={exportPassword}
                      onChange={(e) => setExportPassword(e.target.value)}
                      style={{ maxWidth: 400 }}
                    />
                    <div style={{ marginTop: 4, fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                      设置密码后，备份文件将使用 AES-256-GCM 加密，恢复时需输入相同密码。
                    </div>
                  </div>
                  <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>导出 JSON 备份</Button>
                </Card>
                <Card type="inner" title={<span><FileExcelOutlined /> CSV / Excel 数据导出</span>}>
                  <p style={{ color: 'var(--color-text-secondary)' }}>导出 CSV 或 Excel 格式的明细数据，便于在 Excel/WPS 中二次分析。各列表页也支持按当前筛选条件导出。</p>
                  <Space wrap>
                    <Button icon={<FileTextOutlined />} loading={csvExporting} onClick={handleExportAllTransactionsCSV}>导出交易明细 CSV</Button>
                    <Button icon={<FileTextOutlined />} loading={csvExporting} onClick={handleExportAllCustomersCSV}>导出客户明细 CSV</Button>
                    <Button type="primary" icon={<FileExcelOutlined />} loading={csvExporting} onClick={handleExportFullExcel}>导出全量财务报表 Excel</Button>
                  </Space>
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                    提示：Excel 报表包含 5 个 Sheet（收支总览 / 交易明细 / 商品利润排行 / 客户消费排行 / 返利记录），覆盖全部历史数据。
                  </div>
                </Card>
                <Card type="inner" title={<span><UploadOutlined /> 数据恢复</span>}>
                  <p style={{ color: 'var(--color-text-secondary)' }}>从 JSON 备份文件恢复数据。注意：恢复将覆盖当前所有数据。</p>
                  <UploadButton beforeUpload={handleImportFileSelect} />
                </Card>
                <Card type="inner" title={<span><ExperimentOutlined /> 演示数据</span>}>
                  <p style={{ color: 'var(--color-text-secondary)' }}>生成演示数据以便快速体验系统功能（仅在无数据时可用）。</p>
                  <Popconfirm title="确认生成演示数据？" onConfirm={handleSeed} disabled={hasExistingData}>
                    <Button icon={<ExperimentOutlined />} disabled={hasExistingData}>生成演示数据</Button>
                  </Popconfirm>
                  {hasExistingData && <span style={{ marginLeft: 8, color: 'var(--color-text-tertiary)', fontSize: 12 }}>已有数据，无法生成</span>}
                </Card>
              </Space>
            ),
          },
          {
            key: 'trash',
            label: <span><DeleteOutlined /> 回收站</span>,
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Alert
                  type="info"
                  showIcon
                  message={`回收站说明`}
                  description={`删除的客户、交易、售后工单会在此保留 ${SOFT_DELETE_RETENTION_DAYS} 天，期间可随时恢复。超过 ${SOFT_DELETE_RETENTION_DAYS} 天的记录将在应用启动时自动彻底清理。`}
                />
                <Card type="inner" title={`已删除客户（${trashedCustomers.length}）`} size="small">
                  <Table
                    rowKey="id"
                    size="small"
                    loading={trashLoading}
                    dataSource={trashedCustomers}
                    pagination={false}
                    locale={{ emptyText: <Empty description="无已删除客户" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                    columns={[
                      { title: 'ID', dataIndex: 'id', width: 60 },
                      { title: '昵称', dataIndex: 'xianyu_nickname' },
                      { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                      {
                        title: '操作', width: 160,
                        render: (_: unknown, r: Customer) => (
                          <Space size={0}>
                            <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreCustomer(r.id!)}>恢复</Button>
                            <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeCustomer(r.id!)}>
                              <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </Card>
                <Card type="inner" title={`已删除交易（${trashedTransactions.length}）`} size="small">
                  <Table
                    rowKey="id"
                    size="small"
                    loading={trashLoading}
                    dataSource={trashedTransactions}
                    pagination={false}
                    locale={{ emptyText: <Empty description="无已删除交易" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                    columns={[
                      { title: 'ID', dataIndex: 'id', width: 60 },
                      { title: '商品', dataIndex: 'product_name', ellipsis: true },
                      { title: '售价', dataIndex: 'sale_price', width: 90, render: (v: number) => `¥${v}` },
                      { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                      {
                        title: '操作', width: 160,
                        render: (_: unknown, r: Transaction) => (
                          <Space size={0}>
                            <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreTransaction(r.id!)}>恢复</Button>
                            <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeTransaction(r.id!)}>
                              <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </Card>
                <Card type="inner" title={`已删除售后工单（${trashedAfterSales.length}）`} size="small">
                  <Table
                    rowKey="id"
                    size="small"
                    loading={trashLoading}
                    dataSource={trashedAfterSales}
                    pagination={false}
                    locale={{ emptyText: <Empty description="无已删除工单" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                    columns={[
                      { title: 'ID', dataIndex: 'id', width: 60 },
                      { title: '问题描述', dataIndex: 'issue_desc', ellipsis: true },
                      { title: '关联交易', dataIndex: 'transaction_id', width: 90 },
                      { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                      {
                        title: '操作', width: 160,
                        render: (_: unknown, r: AfterSales) => (
                          <Space size={0}>
                            <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreAfterSales(r.id!)}>恢复</Button>
                            <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeAfterSales(r.id!)}>
                              <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: 'audit',
            label: <span><HistoryOutlined /> 操作日志</span>,
            children: (
              <div>
                <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
                  <Select
                    allowClear
                    placeholder="按模块筛选"
                    style={{ width: 180 }}
                    value={auditModuleFilter}
                    onChange={(v) => { setAuditModuleFilter(v); setAuditPage(1); }}
                    options={[
                      { value: 'transaction', label: '交易管理' },
                      { value: 'customer', label: '客户管理' },
                      { value: 'aftersales', label: '售后管理' },
                      { value: 'rebate', label: '返利管理' },
                      { value: 'warranty', label: '质保管理' },
                      { value: 'settings', label: '系统设置' },
                      { value: 'mail', label: '邮件发送' },
                      { value: 'system', label: '系统' },
                    ]}
                  />
                  <Space>
                    <Button icon={<ReloadOutlined />} onClick={() => loadAuditLogs(auditPage)}>刷新</Button>
                    <Popconfirm title="确认清空所有操作日志？" onConfirm={handleClearLogs}>
                      <Button danger icon={<DeleteOutlined />}>清空</Button>
                    </Popconfirm>
                  </Space>
                </Space>
                <Table
                  rowKey="id"
                  dataSource={auditLogs}
                  size="small"
                  pagination={{
                    current: auditPage,
                    total: auditTotal,
                    pageSize: 50,
                    showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setAuditPage(p); loadAuditLogs(p); },
                  }}
                  locale={{ emptyText: <Empty description="暂无操作日志" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
                  columns={[
                    { title: '时间', dataIndex: 'created_at', width: 160, render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
                    {
                      title: '模块', dataIndex: 'module', width: 100,
                      render: (v: AuditModule) => {
                        const map: Record<string, { text: string; color: string }> = {
                          transaction: { text: '交易', color: 'blue' },
                          customer: { text: '客户', color: 'green' },
                          aftersales: { text: '售后', color: 'orange' },
                          rebate: { text: '返利', color: 'purple' },
                          settings: { text: '设置', color: 'cyan' },
                          mail: { text: '邮件', color: 'geekblue' },
                          warranty: { text: '质保', color: 'gold' },
                          system: { text: '系统', color: 'default' },
                        };
                        const cfg = map[v] || { text: v, color: 'default' };
                        return <Tag color={cfg.color}>{cfg.text}</Tag>;
                      },
                    },
                    { title: '操作', dataIndex: 'action', width: 120 },
                    { title: '对象', dataIndex: 'target_name', width: 140, render: (v?: string) => v || '-' },
                    { title: '详情', dataIndex: 'detail', render: (v?: string) => v ? <Text style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{v}</Text> : '-' },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'security',
            label: <span><SafetyOutlined /> 安全状态</span>,
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Card type="inner" title={<span><SafetyOutlined /> 敏感字段加密</span>}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="SMTP 授权码">
                      <Tag color="green">后端加密存储（AES-256-GCM）</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="GPT 密码 / 邮箱密码">
                      <Tag color="green">后端写入时自动加密</Tag>
                    </Descriptions.Item>
                  </Descriptions>
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginTop: 12 }}
                    message="加密说明"
                    description="敏感字段由 FastAPI 后端使用 AES-256-GCM 加密后写入数据库，密钥保存在后端 data/secret.key。恢复数据时需同时保留数据库与密钥文件。"
                  />
                </Card>
                <Card type="inner" title="数据安全建议">
                  <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--color-text-secondary)', fontSize: 13, lineHeight: 2 }}>
                    <li>定期导出 JSON 备份并妥善保管（含敏感信息，请勿泄露）</li>
                    <li>备份服务器数据时，同时备份数据库文件与 data/secret.key</li>
                    <li>跨设备恢复时使用「数据备份与恢复」功能，并妥善保管备份密码</li>
                  </ul>
                </Card>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="从闲鱼导入商品"
        open={xianyuImportOpen}
        onCancel={() => setXianyuImportOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setXianyuImportOpen(false)}>关闭</Button>,
          <Button key="sync" icon={<ReloadOutlined />} loading={xianyuItemsLoading} onClick={handleSyncXianyuItems}>
            拉取闲鱼商品
          </Button>,
          <Button
            key="import"
            type="primary"
            icon={<CloudUploadOutlined />}
            loading={xianyuImporting}
            disabled={selectedXianyuItemIds.length === 0}
            onClick={handleImportXianyuItems}
          >
            导入选中（{selectedXianyuItemIds.length}）
          </Button>,
        ]}
        width={920}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="商品按闲鱼账号隔离"
          description="先选择账号并拉取商品镜像，再勾选要导入的商品模板。导入会保留来源账号和闲鱼商品 ID，不会跨账号去重或覆盖。"
        />
        <Space style={{ marginBottom: 12 }} wrap>
          <Select
            style={{ width: 240 }}
            placeholder="选择闲鱼账号"
            value={xianyuImportAccountId}
            onChange={(value) => {
              setXianyuImportAccountId(value);
              loadXianyuItems(value);
            }}
            options={xianyuAccounts.map((account) => ({
              value: account.id,
              label: `${account.nickname}${account.unb ? `（${account.unb}）` : ''}`,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={() => loadXianyuItems()} disabled={!xianyuImportAccountId}>
            刷新镜像
          </Button>
          <InputNumber
            min={0}
            precision={2}
            prefix="¥"
            addonBefore="默认成本"
            value={xianyuImportDefaultCost}
            onChange={(value) => setXianyuImportDefaultCost(Number(value ?? 0))}
            style={{ width: 170 }}
          />
          <InputNumber
            min={0}
            max={3650}
            addonBefore="质保天数"
            title="填 0 表示导入模板默认不质保"
            value={xianyuImportWarrantyDays}
            onChange={(value) => setXianyuImportWarrantyDays(Number(value ?? 0))}
            style={{ width: 170 }}
          />
          <Segmented
            size="small"
            value={xianyuItemImportFilter}
            onChange={(value) => {
              setXianyuItemImportFilter(value as XianyuItemTemplateProjectionFilter);
              setSelectedXianyuItemIds([]);
            }}
            options={[
              { label: '未导入', value: 'unimported' },
              { label: '已导入', value: 'imported' },
              { label: '全部', value: 'all' },
            ]}
          />
        </Space>
        <Table
          rowKey="id"
          size="small"
          loading={xianyuItemsLoading}
          dataSource={filteredXianyuItems}
          columns={xianyuItemColumns}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无闲鱼商品镜像，请先点击「拉取闲鱼商品」" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          rowSelection={{
            selectedRowKeys: selectedXianyuItemIds,
            onChange: (keys) => setSelectedXianyuItemIds(keys.map((key) => Number(key))),
            getCheckboxProps: (record: XianyuItem) => ({
              disabled: Boolean(record.projected_template_id),
            }),
          }}
        />
      </Modal>

      <Modal
        title={editingTpl ? '编辑模板' : '新增模板'}
        open={tplModalOpen}
        onCancel={() => { setTplModalOpen(false); setEditingTpl(null); tplForm.resetFields(); }}
        onOk={handleSaveTpl}
        okText="保存"
      >
        <Form form={tplForm} layout="vertical">
          <Form.Item name="name" label="商品名称" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="如：软件激活码（年卡）" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="default_cost" label="默认成本价" rules={[{ required: true }]}>
                <InputNumber min={0} precision={2} prefix="¥" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="default_sale_price" label="建议售价（选填）">
                <InputNumber min={0} precision={2} prefix="¥" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="分类（选填）">
                <Input placeholder="如：激活码" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="warranty_days" label="默认质保天数" tooltip="填 0 表示使用该模板创建订单时默认不质保" rules={[{ required: true }]}>
                <InputNumber min={0} max={3650} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

function UploadButton({ beforeUpload }: { beforeUpload: (file: File) => boolean }) {
  return (
    <Upload
      accept=".json"
      showUploadList={false}
      beforeUpload={(file) => {
        beforeUpload(file);
        return false;
      }}
    >
      <Button icon={<UploadOutlined />}>选择 JSON 文件恢复</Button>
    </Upload>
  );
}
