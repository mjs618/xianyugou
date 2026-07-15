import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Input, Popconfirm, Space, Table, Tag, Typography, message, Modal } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CheckCircleTwoTone,
  CloudServerOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  ReloadOutlined,
  UploadOutlined,
  WarningTwoTone,
} from '@ant-design/icons';
import {
  exportJSON,
  importJSON,
  downloadFile,
  downloadBlob,
  exportTransactionsCSV,
  exportCustomersCSV,
  exportFinanceReportExcel,
} from '@/utils/export';
import { seedDemoData, hasData } from '@/utils/seed';
import { getErrorMessage } from '@/utils/error';
import { isEncryptedBackup } from '@/utils/backupCrypto';
import { getFinanceOverview, getProductProfitStats, getCustomerValueStats } from '@/services/financeService';
import { listTransactions } from '@/services/transactionService';
import { listCustomers } from '@/services/customerService';
import { listRebates } from '@/services/rebateService';
import { listServerBackups, restoreServerBackup } from '@/services/systemService';
import type { ServerBackupInfo } from '@/services/systemService';
import { useAppStore } from '@/store/useAppStore';
import dayjs from 'dayjs';
import UploadButton from './UploadButton';

interface BackupRestoreTabProps {
  /** 容器提供：导入/演示数据成功后调 loadSettings + refreshAll 回填表单 + 刷新全局统计。
   *
   * 注意（D2 决策 A）：本 Tab 不负责刷新 ProductTemplateTab 的模板列表 ——
   * 后者重激活时会自动 mount 重载，符合 antd Tabs 默认行为。
   */
  onDataReset: () => Promise<void>;
}

/** 字节大小格式化（如 1.5 MB / 320 KB）。 */
function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** 数据备份与恢复 Tab：JSON 导出（含加密）/ CSV+Excel 导出 / JSON 恢复（含解密）/ 演示数据。
 *
 * 状态自包含：exportPassword / importFileContent / importPasswordRef / hasExistingData / csvExporting /
 * serverBackups / loadingBackups / restoring（E6 服务器备份恢复）。
 */
export default function BackupRestoreTab({ onDataReset }: BackupRestoreTabProps) {
  const { refreshAll } = useAppStore();
  const [exportPassword, setExportPassword] = useState('');
  const [importFileContent, setImportFileContent] = useState<string | null>(null);
  // P1 修复：Modal.confirm 是非受控渲染，弹窗内的输入框 value 不会随 state 更新；
  // 用 ref 在 onChange 时同步最新值，确保 onOk 时读到的是用户实际输入的密码
  const importPasswordRef = useRef('');
  const [hasExistingData, setHasExistingData] = useState(false);
  const [csvExporting, setCsvExporting] = useState(false);
  // E6 服务器备份恢复：从后端 data/backups/daily/*.db 文件级整库恢复（灾难恢复）
  const [serverBackups, setServerBackups] = useState<ServerBackupInfo[]>([]);
  const [loadingBackups, setLoadingBackups] = useState(false);
  const [restoring, setRestoring] = useState(false);

  useEffect(() => {
    hasData().then(setHasExistingData);
    void loadServerBackups();
  }, []);

  /** 加载服务器备份列表。失败时静默（可选功能，不阻塞页面）。 */
  const loadServerBackups = async () => {
    setLoadingBackups(true);
    try {
      const resp = await listServerBackups();
      setServerBackups(resp.backups);
    } catch (err) {
      console.warn('加载服务器备份列表失败:', err);
    } finally {
      setLoadingBackups(false);
    }
  };

  /** 从服务器备份恢复数据库（不可逆）。恢复成功后强制刷新整个页面。 */
  const handleRestoreServerBackup = async (filename: string) => {
    setRestoring(true);
    try {
      const report = await restoreServerBackup(filename);
      if (report.success) {
        // 数据库已被整库覆盖，所有前端缓存（zustand store / React state）失效
        // 必须刷新整个页面，不能只调 refreshAll（ORM 缓存、连接池等也需重置）
        Modal.success({
          title: '数据库已恢复',
          content: (
            <div>
              <p>{report.message}</p>
              {report.table_counts && (
                <p style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>
                  表行数：{Object.entries(report.table_counts)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(' / ')}
                </p>
              )}
              <p style={{ color: 'var(--color-warning)' }}>页面将刷新以加载恢复后的最新数据。</p>
            </div>
          ),
          okText: '立即刷新',
          onOk: () => window.location.reload(),
        });
      } else {
        message.error(report.message || '恢复失败');
      }
    } catch (err) {
      message.error('恢复失败：' + getErrorMessage(err, '未知错误'));
    } finally {
      setRestoring(false);
    }
  };

  /** 服务器备份表列定义。 */
  const backupColumns: ColumnsType<ServerBackupInfo> = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (name: string) => <Typography.Text code>{name}</Typography.Text>,
    },
    {
      title: '大小',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 90,
      render: (size: number) => formatBytes(size),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (iso: string) => dayjs(iso).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '完整性',
      dataIndex: 'integrity_ok',
      key: 'integrity_ok',
      width: 90,
      render: (ok: boolean) =>
        ok ? (
          <Tag icon={<CheckCircleTwoTone twoToneColor="#52c41a" />} color="success">正常</Tag>
        ) : (
          <Tag icon={<WarningTwoTone twoToneColor="#ff4d4f" />} color="error">异常</Tag>
        ),
    },
    {
      title: '表行数',
      dataIndex: 'table_counts',
      key: 'table_counts',
      render: (counts: Record<string, number>) =>
        Object.keys(counts).length === 0 ? (
          <Typography.Text type="secondary">无 manifest</Typography.Text>
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {Object.entries(counts)
              .map(([k, v]) => `${k}:${v}`)
              .join(' · ')}
          </Typography.Text>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) => (
        <Popconfirm
          title="确认从此备份恢复？"
          description={
            <div style={{ maxWidth: 280 }}>
              <p style={{ color: 'var(--color-error)' }}>此操作不可逆，将覆盖当前数据库。</p>
              <p style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>
                恢复前会自动备份当前数据到 .pre_restore.bak，可用于回退。
              </p>
            </div>
          }
          okText="确认恢复"
          okType="danger"
          cancelText="取消"
          disabled={!record.integrity_ok || restoring}
          onConfirm={() => handleRestoreServerBackup(record.filename)}
        >
          <Button
            type="link"
            danger
            size="small"
            loading={restoring}
            disabled={!record.integrity_ok}
          >
            恢复
          </Button>
        </Popconfirm>
      ),
    },
  ];

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
      await onDataReset();
      setHasExistingData(await hasData());
      // 清空状态
      setImportFileContent(null);
      importPasswordRef.current = '';
    } catch (err: unknown) {
      message.error('恢复失败：' + getErrorMessage(err, '文件格式错误'));
    }
  };

  const handleSeed = async () => {
    try {
      await seedDemoData();
      message.success('演示数据已生成');
      await onDataReset();
      setHasExistingData(await hasData());
    } catch (err) {
      console.error('生成演示数据失败:', err);
      message.error(err instanceof Error ? err.message : '生成失败');
    }
  };

  // CSV/Excel 数据导出（P3-1：在设置页提供统一入口，便于一次性导出全量数据）
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

  return (
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
      <Card
        type="inner"
        title={
          <span>
            <CloudServerOutlined /> 服务器备份恢复（灾难恢复）
          </span>
        }
        extra={
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={loadingBackups}
            onClick={loadServerBackups}
          >
            刷新列表
          </Button>
        }
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="文件级整库恢复：从服务器自动备份（data/backups/daily/*.db）恢复整个数据库"
          description="这是灾难恢复手段，会覆盖当前数据库的所有数据。与上方「JSON 恢复」不同，后者是应用层数据导入。恢复前会自动备份当前数据到 .pre_restore.bak（可用于回退）。"
        />
        <Table<ServerBackupInfo>
          rowKey="filename"
          columns={backupColumns}
          dataSource={serverBackups}
          loading={loadingBackups}
          size="small"
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: '暂无服务器备份（备份调度器每日自动生成，可在「运行状态」查看最近备份时间）' }}
        />
      </Card>
    </Space>
  );
}
