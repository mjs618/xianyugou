import { useEffect, useState } from 'react';
import { Card, Space, Descriptions, Tag, Form, Input, Button, Popconfirm, Alert, message } from 'antd';
import { KeyOutlined, SafetyOutlined, DeleteOutlined } from '@ant-design/icons';
import { getTokenStatus, verifyToken } from '@/services/authService';
import { getApiToken, setApiToken, clearApiToken } from '@/services/apiClient';

/** API 安全 Tab：管理本地会话 Token 与后端 Token 状态。状态自包含。
 *
 * 行为变化（与原 Settings.tsx 一致）：原在容器初始 Promise.all 中加载 token 状态，
 * 现改为本 Tab 首次挂载时加载 —— 与 audit/trash 的 activeTab 监听行为等价。
 */
export default function ApiTokenTab() {
  // P0-1 API Token 配置：当前后端是否已配置 token、用户输入、测试中
  const [apiTokenConfigured, setApiTokenConfigured] = useState<boolean | null>(null);
  const [apiTokenInput, setApiTokenInput] = useState('');
  const [apiTokenTesting, setApiTokenTesting] = useState(false);

  // P0-1 查询后端 token 配置状态（首次挂载时拉取，失败保持 null 不阻塞）
  const loadTokenStatus = async () => {
    try {
      const status = await getTokenStatus();
      setApiTokenConfigured(status.token_configured);
    } catch {
      // 后端不可用时保持 null（未知），不阻塞设置页加载
    }
  };

  useEffect(() => {
    loadTokenStatus();
  }, []);

  // P0-1 测试并保存 API Token：调后端校验，成功则持久化到 sessionStorage
  const handleTestAndSaveToken = async () => {
    const token = apiTokenInput.trim();
    if (!token) {
      message.warning('请输入 API Token');
      return;
    }
    setApiTokenTesting(true);
    try {
      const result = await verifyToken(token);
      if (result.valid) {
        setApiToken(token);
        setApiTokenConfigured(true);
        message.success('Token 校验通过，已保存到当前会话');
        setApiTokenInput('');
      } else {
        message.error('Token 校验失败：与后端不匹配');
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '校验失败，请确认后端已启动');
    } finally {
      setApiTokenTesting(false);
    }
  };

  // P0-1 清除已保存的 API Token（用于切换账号或排查问题）
  const handleClearToken = () => {
    clearApiToken();
    setApiTokenConfigured(null);
    setApiTokenInput('');
    message.success('已清除本地保存的 Token，下次请求将返回 401');
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card type="inner" title={<span><KeyOutlined /> API Token 配置</span>}>
        <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
          <Descriptions.Item label="后端 Token 状态">
            {apiTokenConfigured === null ? (
              <Tag color="default">未知（后端不可达）</Tag>
            ) : apiTokenConfigured ? (
              <Tag color="green">已配置</Tag>
            ) : (
              <Tag color="orange">未配置</Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="本地会话 Token">
            {getApiToken() ? (
              <Tag color="blue">已保存（{getApiToken()!.slice(0, 6)}…）</Tag>
            ) : (
              <Tag>未保存</Tag>
            )}
          </Descriptions.Item>
        </Descriptions>
        <Form layout="vertical" style={{ maxWidth: 600 }}>
          <Form.Item label="API Token" help="粘贴从后端 data/api.token 获取的 token">
            <Input.Password
              placeholder="输入 API Token"
              value={apiTokenInput}
              onChange={(e) => setApiTokenInput(e.target.value)}
              visibilityToggle
              autoComplete="off"
            />
          </Form.Item>
          <Space>
            <Button
              type="primary"
              icon={<SafetyOutlined />}
              loading={apiTokenTesting}
              disabled={!apiTokenInput.trim()}
              onClick={handleTestAndSaveToken}
            >
              测试并保存
            </Button>
            <Popconfirm
              title="确认清除本地保存的 Token？"
              okText="清除"
              okType="danger"
              onConfirm={handleClearToken}
            >
              <Button danger icon={<DeleteOutlined />} disabled={!getApiToken()}>
                清除本地 Token
              </Button>
            </Popconfirm>
          </Space>
        </Form>
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 16 }}
          message="如何获取 API Token"
          description={
            <div style={{ fontSize: 12, lineHeight: 1.8 }}>
              <p style={{ margin: 0 }}>后端首次启动时会自动生成 Token 并持久化到 <code>data/api.token</code>。获取方式：</p>
              <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                <li>Docker 部署：<code>docker exec xianyugou-backend cat /app/data/api.token</code></li>
                <li>本地开发：查看 <code>server/backend/data/api.token</code> 文件</li>
              </ul>
              <p style={{ margin: '8px 0 0' }}>Token 保存在 sessionStorage（关闭浏览器即清除），所有 API 请求自动注入 <code>X-API-Token</code> 头。</p>
            </div>
          }
        />
      </Card>
    </Space>
  );
}
