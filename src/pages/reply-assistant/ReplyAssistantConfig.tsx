import { useEffect, useState } from 'react';
import {
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import {
  createReplyRule,
  deleteReplyRule,
  updateReplyAssistantSettings,
  updateReplyRule,
} from '@/services/replyAssistantService';
import type {
  ProductTemplate,
  ReplyAssistantSettings,
  ReplyRule,
  ReplyRuleInput,
} from '@/types';


interface ReplyAssistantConfigProps {
  open: boolean;
  settings: ReplyAssistantSettings;
  rules: ReplyRule[];
  templates: ProductTemplate[];
  onClose: () => void;
  onReload: () => Promise<void>;
}

export default function ReplyAssistantConfig({
  open,
  settings,
  rules,
  templates,
  onClose,
  onReload,
}: ReplyAssistantConfigProps) {
  const [settingsForm] = Form.useForm();
  const [ruleForm] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<ReplyRule | null>(null);

  useEffect(() => {
    if (open) settingsForm.setFieldsValue({ ...settings, api_key: '' });
  }, [open, settings, settingsForm]);

  const saveSettings = async () => {
    try {
      const values = await settingsForm.validateFields();
      if (!values.api_key) delete values.api_key;
      setSaving(true);
      await updateReplyAssistantSettings(values);
      await onReload();
      message.success('回复助手配置已保存');
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const openRuleModal = (rule?: ReplyRule) => {
    setEditingRule(rule || null);
    ruleForm.setFieldsValue(rule
      ? { ...rule, keywords: rule.keywords.join('，') }
      : { enabled: true, priority: 0 });
    setRuleModalOpen(true);
  };

  const saveRule = async () => {
    try {
      const values = await ruleForm.validateFields();
      const input: ReplyRuleInput = {
        ...values,
        keywords: String(values.keywords)
          .split(/[，,]/)
          .map((item) => item.trim())
          .filter(Boolean),
      };
      if (editingRule) await updateReplyRule(editingRule.id, input);
      else await createReplyRule(input);
      setRuleModalOpen(false);
      await onReload();
      message.success(editingRule ? '规则已更新' : '规则已创建');
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    }
  };

  const removeRule = async (id: number) => {
    try {
      await deleteReplyRule(id);
      await onReload();
      message.success('规则已删除');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除失败');
    }
  };

  return (
    <Drawer
      title="回复助手配置"
      width={640}
      open={open}
      onClose={onClose}
      destroyOnClose={false}
    >
      <Tabs items={[
        {
          key: 'settings',
          label: '运行与 AI',
          children: (
            <Form form={settingsForm} layout="vertical" onFinish={saveSettings}>
              <Form.Item name="enabled" label="回复助手" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Form.Item name="ai_enabled" label="AI 兜底" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="停用" />
              </Form.Item>
              <Form.Item
                name="api_base_url"
                label="API Base URL"
                extra="远程地址必须使用 HTTPS；可填写 OpenAI-compatible /v1 地址。"
              >
                <Input placeholder="https://example.com/v1" />
              </Form.Item>
              <Form.Item
                name="api_key"
                label="API Key"
                extra={settings.api_key_configured ? '已配置；留空保持原密钥不变。' : '尚未配置。'}
              >
                <Input.Password autoComplete="new-password" placeholder="仅保存到后端加密存储" />
              </Form.Item>
              <Form.Item name="model" label="模型">
                <Input placeholder="模型名称" />
              </Form.Item>
              <Form.Item name="system_prompt" label="补充指令">
                <Input.TextArea rows={5} maxLength={4000} showCount />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>保存配置</Button>
            </Form>
          ),
        },
        {
          key: 'rules',
          label: `固定规则 ${rules.length}`,
          children: (
            <>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openRuleModal()}>
                新建规则
              </Button>
              <List
                className="reply-rule-list"
                dataSource={rules}
                locale={{ emptyText: '暂无固定规则' }}
                renderItem={(rule) => (
                  <List.Item actions={[
                    <Button key="edit" type="text" icon={<EditOutlined />} aria-label={`编辑${rule.name}`} onClick={() => openRuleModal(rule)} />,
                    <Popconfirm key="delete" title="确认删除这条规则？" onConfirm={() => removeRule(rule.id)}>
                      <Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除${rule.name}`} />
                    </Popconfirm>,
                  ]}>
                    <List.Item.Meta
                      title={<Space><span>{rule.name}</span>{!rule.enabled && <Tag>停用</Tag>}</Space>}
                      description={
                        <Space direction="vertical" size={2}>
                          <Typography.Text type="secondary">关键词：{rule.keywords.join('、')}</Typography.Text>
                          <Typography.Text ellipsis>{rule.reply_text}</Typography.Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </>
          ),
        },
      ]} />

      <Modal
        title={editingRule ? '编辑固定规则' : '新建固定规则'}
        open={ruleModalOpen}
        onCancel={() => setRuleModalOpen(false)}
        onOk={saveRule}
        okText="保存"
      >
        <Form form={ruleForm} layout="vertical">
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="keywords" label="关键词" extra="使用中文或英文逗号分隔" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="reply_text" label="固定回复" rules={[{ required: true }]}>
            <Input.TextArea rows={4} maxLength={1000} showCount />
          </Form.Item>
          <Form.Item name="product_template_id" label="限定商品模板">
            <Select
              allowClear
              options={templates
                .filter((item) => item.id !== undefined)
                .map((item) => ({ value: item.id!, label: item.name }))}
            />
          </Form.Item>
          <Space>
            <Form.Item name="priority" label="优先级">
              <InputNumber min={-1000} max={1000} />
            </Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Drawer>
  );
}
