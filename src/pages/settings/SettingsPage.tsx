import { useEffect, useState } from 'react';
import { Card, Tabs, Form, Skeleton } from 'antd';
import {
  AppstoreOutlined,
  BellOutlined,
  BgColorsOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  HistoryOutlined,
  KeyOutlined,
  MailOutlined,
  SafetyOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { getSettings } from '@/services/settingsService';
import { useAppStore } from '@/store/useAppStore';
import type { Settings } from '@/types';
import ThemeTab from './ThemeTab';
import NotificationTab from './NotificationTab';
import ApiTokenTab from './ApiTokenTab';
import SecurityStatusTab from './SecurityStatusTab';
import SystemSettingsTab from './SystemSettingsTab';
import MailConfigTab from './MailConfigTab';
import AuditLogTab from './AuditLogTab';
import BackupRestoreTab from './BackupRestoreTab';
import TrashTab from './TrashTab';
import ProductTemplateTab from './ProductTemplateTab';

export default function SettingsPage() {
  const { refreshAll } = useAppStore();
  const [activeTab, setActiveTab] = useState('theme');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [settingsForm] = Form.useForm();
  const [mailForm] = Form.useForm();

  const loadSettings = async () => {
    const s = await getSettings();
    setSettings(s);
    settingsForm.setFieldsValue(s);
    mailForm.setFieldsValue(s);
  };

  // 供 SystemSettingsTab / MailConfigTab 保存后回调：重新拉取 settings 并回填两个 form
  // （SystemSettingsTab 内部已调 refreshAll，这里只负责回填表单；MailConfigTab 不调 refreshAll）
  const reloadSettings = async () => {
    await loadSettings();
  };

  // 供 BackupRestoreTab 导入/演示数据后回调：刷新全局统计 + 回填 settings 表单
  // （hasExistingData 由 BackupRestoreTab 自己管理；ProductTemplateTab 重激活时自动重载，按 D2 决策 A）
  const onDataReset = async () => {
    refreshAll();
    await loadSettings();
  };

  // 仅加载 settings（loadTemplates / loadXianyuAccountOptions 已下沉到 ProductTemplateTab mount effect）
  useEffect(() => {
    loadSettings().finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card title="系统设置">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    );
  }

  return (
    <Card title="系统设置">
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'theme',
            label: <span><BgColorsOutlined /> 主题</span>,
            children: <ThemeTab />,
          },
          {
            key: 'templates',
            label: <span><AppstoreOutlined /> 商品模板</span>,
            children: <ProductTemplateTab defaultWarrantyDays={settings?.warranty_days ?? 30} />,
          },
          {
            key: 'system',
            label: <span><SettingOutlined /> 系统设置</span>,
            children: <SystemSettingsTab form={settingsForm} onSaved={reloadSettings} />,
          },
          {
            key: 'mail',
            label: <span><MailOutlined /> 邮件配置</span>,
            children: <MailConfigTab form={mailForm} onSaved={reloadSettings} />,
          },
          {
            key: 'notification',
            label: <span><BellOutlined /> 通知设置</span>,
            children: <NotificationTab />,
          },
          {
            key: 'backup',
            label: <span><DatabaseOutlined /> 数据备份与恢复</span>,
            children: <BackupRestoreTab onDataReset={onDataReset} />,
          },
          {
            key: 'trash',
            label: <span><DeleteOutlined /> 回收站</span>,
            children: <TrashTab />,
          },
          {
            key: 'audit',
            label: <span><HistoryOutlined /> 操作日志</span>,
            children: <AuditLogTab />,
          },
          {
            key: 'api-security',
            label: <span><KeyOutlined /> API 安全</span>,
            children: <ApiTokenTab />,
          },
          {
            key: 'security',
            label: <span><SafetyOutlined /> 安全状态</span>,
            children: <SecurityStatusTab />,
          },
        ]}
      />
    </Card>
  );
}
