import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { CopyOutlined, SendOutlined } from '@ant-design/icons';
import type {
  ProductTemplate,
  ReplyRiskCheck,
  ReplySuggestion,
  ReplySuggestionInput,
  XianyuAccount,
} from '@/types';


interface ReplyComposerProps {
  accounts: XianyuAccount[];
  templates: ProductTemplate[];
  assistantEnabled: boolean;
  loading: boolean;
  onGenerate: (input: ReplySuggestionInput) => Promise<ReplySuggestion>;
  onCheckRisk: (text: string) => Promise<ReplyRiskCheck>;
}

export default function ReplyComposer({
  accounts,
  templates,
  assistantEnabled,
  loading,
  onGenerate,
  onCheckRisk,
}: ReplyComposerProps) {
  const [accountId, setAccountId] = useState<number>();
  const [productId, setProductId] = useState<number>();
  const [buyerMessage, setBuyerMessage] = useState('');
  const [contextText, setContextText] = useState('');
  const [suggestion, setSuggestion] = useState<ReplySuggestion | null>(null);
  const [candidate, setCandidate] = useState('');
  const [checkingRisk, setCheckingRisk] = useState(false);

  useEffect(() => {
    if (accountId === undefined && accounts[0]) setAccountId(accounts[0].id);
  }, [accountId, accounts]);

  const selectedAccount = accounts.find((account) => account.id === accountId);

  const clearSuggestion = () => {
    setSuggestion(null);
    setCandidate('');
  };

  const parseContext = () => {
    const lines = contextText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (lines.length > 10) {
      message.warning('近期上下文最多 10 条');
      return null;
    }
    const parsed = lines.map((line) => {
      const seller = line.match(/^卖家[：:]\s*(.*)$/);
      const buyer = line.match(/^买家[：:]\s*(.*)$/);
      return {
        role: seller ? 'seller' as const : 'user' as const,
        content: (seller?.[1] ?? buyer?.[1] ?? line).trim(),
      };
    });
    if (parsed.some((item) => !item.content || item.content.length > 1000)) {
      message.warning('每条近期上下文需为 1–1000 个字符');
      return null;
    }
    return parsed;
  };

  const generate = async () => {
    const trimmed = buyerMessage.trim();
    if (!accountId) {
      message.warning('请先选择闲鱼账号');
      return;
    }
    if (!trimmed) {
      message.warning('请填写买家消息');
      return;
    }
    const contextMessages = parseContext();
    if (contextMessages === null) return;
    clearSuggestion();
    try {
      const input: ReplySuggestionInput = {
        account_id: accountId,
        buyer_message: trimmed,
      };
      if (productId) input.product_template_id = productId;
      if (contextMessages.length) input.context_messages = contextMessages;
      const result = await onGenerate(input);
      setSuggestion(result);
      setCandidate(result.reply);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '生成候选失败');
    }
  };

  const writeClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success('候选回复已复制，请到闲鱼人工核对后发送');
    } catch {
      message.error('复制失败，请手动选择文本');
    }
  };

  const copy = async () => {
    const text = candidate.trim();
    if (!text || checkingRisk) return;
    setCheckingRisk(true);
    try {
      const result = await onCheckRisk(text);
      if (result.risk_level === 'normal') {
        await writeClipboard(text);
        return;
      }
      const reasons = result.risk_reasons.join('、');
      Modal.confirm({
        title: '候选回复包含风险内容',
        content: `触发原因：${reasons}。请再次核对后再复制。`,
        okText: '已核对，继续复制',
        cancelText: '取消复制',
        okType: 'danger',
        onOk: () => writeClipboard(text),
      });
    } catch {
      message.error('风险检查失败，请手动选择文本');
    } finally {
      setCheckingRisk(false);
    }
  };

  return (
    <Card className="reply-workbench-card" bordered={false}>
      <div className="reply-workbench-grid">
        <section className="reply-input-panel" aria-labelledby="reply-input-title">
          <div className="reply-section-heading">
            <span className="reply-step">01</span>
            <div>
              <Typography.Title level={4} id="reply-input-title">买家消息</Typography.Title>
              <Typography.Text type="secondary">选择业务上下文，再粘贴最新一条消息</Typography.Text>
            </div>
          </div>

          <Form layout="vertical">
            <div className="reply-context-row">
              <Form.Item label="闲鱼账号" required>
                <Select
                  aria-label="闲鱼账号"
                  value={accountId}
                  onChange={(value) => {
                    setAccountId(value);
                    clearSuggestion();
                  }}
                  options={accounts.map((account) => ({
                    value: account.id,
                    label: `${account.nickname}${account.status === 'paused' ? ' · 已暂停' : ''}`,
                  }))}
                  placeholder="选择账号"
                />
              </Form.Item>
              <Form.Item label="商品模板（可选）">
                <Select
                  aria-label="商品模板"
                  allowClear
                  value={productId}
                  onChange={(value) => {
                    setProductId(value);
                    clearSuggestion();
                  }}
                  options={templates
                    .filter((item) => item.id !== undefined)
                    .map((item) => ({ value: item.id!, label: item.name }))}
                  placeholder="用于匹配商品专属规则"
                />
              </Form.Item>
            </div>
            {selectedAccount?.status === 'paused' && (
              <Alert
                type="warning"
                showIcon
                message="账号同步已暂停，但仍可生成候选；本功能不会访问闲鱼网络。"
                className="reply-inline-alert"
              />
            )}
            <Form.Item
              label="近期上下文（可选）"
              extra="每行一条，使用“买家：”或“卖家：”标注角色，最多 10 条。"
            >
              <Input.TextArea
                value={contextText}
                onChange={(event) => {
                  setContextText(event.target.value);
                  clearSuggestion();
                }}
                placeholder="每行一条，例如：买家：想了解一下"
                rows={4}
              />
            </Form.Item>
            <Form.Item label="最新买家消息" required>
              <Input.TextArea
                value={buyerMessage}
                onChange={(event) => {
                  setBuyerMessage(event.target.value);
                  clearSuggestion();
                }}
                placeholder="粘贴买家的最新消息"
                rows={7}
                maxLength={2000}
                showCount
              />
            </Form.Item>
            <Button
              type="primary"
              size="large"
              block
              icon={<SendOutlined />}
              loading={loading}
              disabled={!assistantEnabled || !accountId || !buyerMessage.trim()}
              onClick={generate}
              aria-label="生成候选回复"
            >
              生成候选回复
            </Button>
          </Form>
        </section>

        <section className="reply-output-panel" aria-labelledby="reply-output-title">
          <div className="reply-section-heading">
            <span className="reply-step">02</span>
            <div>
              <Typography.Title level={4} id="reply-output-title">候选回复</Typography.Title>
              <Typography.Text type="secondary">先编辑核对，再复制到闲鱼发送</Typography.Text>
            </div>
          </div>

          {!suggestion ? (
            <div className="reply-empty-state">
              <span className="reply-empty-mark">候选区</span>
              <Typography.Text type="secondary">
                命中固定规则时不会调用 AI；未命中时才按配置生成。
              </Typography.Text>
            </div>
          ) : (
            <div className="reply-result">
              <Space wrap className="reply-result-tags">
                <Tag color={suggestion.source === 'rule' ? 'green' : 'blue'}>
                  {suggestion.source === 'rule' ? '固定规则' : 'AI 候选'}
                </Tag>
                <Tag>{suggestion.reply.length} 字</Tag>
              </Space>
              {suggestion.risk_level === 'manual_required' && (
                <Alert
                  type="warning"
                  showIcon
                  message="人工核对"
                  description={`触发原因：${suggestion.risk_reasons.join('、')}`}
                />
              )}
              <Input.TextArea
                aria-label="候选回复"
                value={candidate}
                onChange={(event) => setCandidate(event.target.value)}
                rows={8}
                maxLength={1000}
                showCount
              />
              <Button
                size="large"
                block
                icon={<CopyOutlined />}
                loading={checkingRisk}
                onClick={copy}
                aria-label="复制候选回复"
              >
                复制候选回复
              </Button>
            </div>
          )}
        </section>
      </div>
    </Card>
  );
}
