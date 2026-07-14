import { useEffect, useState } from 'react';
import { Button, Empty, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd';
import { DeleteOutlined, HistoryOutlined, ReloadOutlined } from '@ant-design/icons';
import { listLogs, clearLogs, getLogCount } from '@/services/auditLogService';
import type { AuditModule, OperationLog } from '@/types';
import dayjs from 'dayjs';

const { Text } = Typography;

const MODULE_OPTIONS = [
  { value: 'transaction', label: '交易管理' },
  { value: 'customer', label: '客户管理' },
  { value: 'aftersales', label: '售后管理' },
  { value: 'rebate', label: '返利管理' },
  { value: 'warranty', label: '质保管理' },
  { value: 'settings', label: '系统设置' },
  { value: 'mail', label: '邮件发送' },
  { value: 'system', label: '系统' },
];

const MODULE_LABEL_MAP: Record<string, { text: string; color: string }> = {
  transaction: { text: '交易', color: 'blue' },
  customer: { text: '客户', color: 'green' },
  aftersales: { text: '售后', color: 'orange' },
  rebate: { text: '返利', color: 'purple' },
  settings: { text: '设置', color: 'cyan' },
  mail: { text: '邮件', color: 'geekblue' },
  warranty: { text: '质保', color: 'gold' },
  system: { text: '系统', color: 'default' },
};

/** 操作日志 Tab：分页表格 + 模块筛选 + 清空。状态自包含。
 *
 * 原容器通过 `useEffect([activeTab, auditModuleFilter])` 在切到 audit Tab 时加载，
 * 拆分后改为本组件 mount effect —— 子组件挂载即等价于「Tab 被激活」。
 * 模块筛选变化时也触发重载（page 重置为 1）。
 */
export default function AuditLogTab() {
  const [auditLogs, setAuditLogs] = useState<OperationLog[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditModuleFilter, setAuditModuleFilter] = useState<AuditModule | undefined>(undefined);

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

  // mount + 模块筛选变化时重载（page 重置为 1）
  useEffect(() => {
    loadAuditLogs(1);
    setAuditPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditModuleFilter]);

  const handleClearLogs = async () => {
    await clearLogs();
    message.success('操作日志已清空');
    loadAuditLogs(1);
    setAuditPage(1);
  };

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Select
          allowClear
          placeholder="按模块筛选"
          style={{ width: 180 }}
          value={auditModuleFilter}
          onChange={(v) => { setAuditModuleFilter(v); setAuditPage(1); }}
          options={MODULE_OPTIONS}
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
              const cfg = MODULE_LABEL_MAP[v] || { text: v, color: 'default' };
              return <Tag color={cfg.color}>{cfg.text}</Tag>;
            },
          },
          { title: '操作', dataIndex: 'action', width: 120 },
          { title: '对象', dataIndex: 'target_name', width: 140, render: (v?: string) => v || '-' },
          { title: '详情', dataIndex: 'detail', render: (v?: string) => v ? <Text style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{v}</Text> : '-' },
        ]}
      />
    </div>
  );
}
