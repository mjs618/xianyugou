import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Result, Skeleton, Space, Tag, Typography } from 'antd';
import { ControlOutlined, MessageOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { listActiveTemplates } from '@/services/productTemplateService';
import {
  generateReplySuggestion,
  getReplyAssistantSettings,
  listReplyRules,
} from '@/services/replyAssistantService';
import { listAccounts } from '@/services/xianyuService';
import type {
  ProductTemplate,
  ReplyAssistantSettings,
  ReplyRule,
  ReplySuggestionInput,
  XianyuAccount,
} from '@/types';
import ReplyAssistantConfig from './ReplyAssistantConfig';
import ReplyComposer from './ReplyComposer';
import './replyAssistant.css';


export default function ReplyAssistantPage() {
  const [settings, setSettings] = useState<ReplyAssistantSettings | null>(null);
  const [rules, setRules] = useState<ReplyRule[]>([]);
  const [accounts, setAccounts] = useState<XianyuAccount[]>([]);
  const [templates, setTemplates] = useState<ProductTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  const loadData = useCallback(async () => {
    const [nextSettings, nextRules, nextAccounts, nextTemplates] = await Promise.all([
      getReplyAssistantSettings(),
      listReplyRules(),
      listAccounts(),
      listActiveTemplates(),
    ]);
    setSettings(nextSettings);
    setRules(nextRules);
    setAccounts(nextAccounts);
    setTemplates(nextTemplates);
  }, []);

  useEffect(() => {
    void loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    setLoadError('');
    try {
      await loadData();
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : '加载回复助手失败');
    } finally {
      setLoading(false);
    }
  };

  const generate = async (input: ReplySuggestionInput) => {
    setGenerating(true);
    try {
      return await generateReplySuggestion(input);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  if (loadError || !settings) {
    return (
      <Result
        status="warning"
        title="回复助手加载失败"
        subTitle={loadError || '未获取到回复助手配置'}
        extra={<Button type="primary" onClick={loadInitialData}>重新加载</Button>}
      />
    );
  }

  return (
    <div className="reply-assistant-page">
      <header className="reply-page-header">
        <div>
          <div className="reply-eyebrow"><MessageOutlined /> REPLY WORKBENCH</div>
          <Typography.Title level={2}>闲鱼回复助手</Typography.Title>
          <Typography.Paragraph>
            用固定规则快速响应，用 AI 补齐长尾问题；所有回复都由你最终确认。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Tag color={settings.enabled ? 'success' : 'default'}>
            {settings.enabled ? '助手已启用' : '助手未启用'}
          </Tag>
          <Tag icon={<SafetyCertificateOutlined />} color="orange">人工发送</Tag>
          <Button
            icon={<ControlOutlined />}
            onClick={() => setConfigOpen(true)}
            aria-label="配置回复助手"
          >
            配置
          </Button>
        </Space>
      </header>

      <Alert
        className="reply-boundary-alert"
        type="info"
        showIcon
        message="只生成候选，不会自动发送，也不会读取闲鱼 Cookie 或会话。"
      />
      {!settings.enabled && (
        <Alert
          className="reply-boundary-alert"
          type="warning"
          showIcon
          message="回复助手当前停用，请先在配置中启用。"
        />
      )}
      {accounts.length === 0 && (
        <Alert
          className="reply-boundary-alert"
          type="warning"
          showIcon
          message="暂无闲鱼账号，请先到订单同步页面添加账号。"
        />
      )}

      <ReplyComposer
        accounts={accounts}
        templates={templates}
        assistantEnabled={settings.enabled}
        loading={generating}
        onGenerate={generate}
      />

      <ReplyAssistantConfig
        open={configOpen}
        settings={settings}
        rules={rules}
        templates={templates}
        onClose={() => setConfigOpen(false)}
        onReload={loadData}
      />
    </div>
  );
}
