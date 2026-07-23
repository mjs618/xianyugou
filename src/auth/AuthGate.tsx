import { useCallback, useEffect, useState, type PropsWithChildren } from 'react';
import { Alert, Button, Card, Form, Input, Result, Spin, Typography } from 'antd';
import { getTokenStatus, verifyToken } from '@/services/authService';
import { getApiToken, setApiToken, subscribeAuthRequired } from '@/services/apiClient';

type AuthStatus = 'checking' | 'locked' | 'offline' | 'authenticated';

interface UnlockFormValues {
  token: string;
}

export default function AuthGate({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [tokenConfigured, setTokenConfigured] = useState(true);
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  const checkBackend = useCallback(async () => {
    setStatus('checking');
    setError(undefined);

    if (getApiToken()) {
      setStatus('authenticated');
      return;
    }

    try {
      const result = await getTokenStatus();
      setTokenConfigured(result.token_configured);
      setStatus('locked');
    } catch {
      setStatus('offline');
    }
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeAuthRequired(() => {
      setError('当前会话认证已失效，请重新输入 API Token。');
      setStatus('locked');
    });
    void checkBackend();
    return unsubscribe;
  }, [checkBackend]);

  const handleUnlock = async ({ token }: UnlockFormValues) => {
    const normalizedToken = token.trim();
    setSubmitting(true);
    setError(undefined);
    try {
      const result = await verifyToken(normalizedToken);
      if (!result.valid) {
        setError('API Token 不正确，请重新输入。');
        return;
      }
      setApiToken(normalizedToken);
      setStatus('authenticated');
    } catch {
      setError('验证失败，请确认后端服务可用后重试。');
    } finally {
      setSubmitting(false);
    }
  };

  if (status === 'authenticated') {
    return <>{children}</>;
  }

  if (status === 'checking') {
    return (
      <main className="auth-gate" aria-label="系统认证">
        <Spin size="large" tip="正在检测服务">
          <div className="auth-gate-loading" />
        </Spin>
      </main>
    );
  }

  if (status === 'offline') {
    return (
      <main className="auth-gate" aria-label="系统认证">
        <Card className="auth-gate-card">
          <Result
            status="warning"
            title="后端服务不可达"
            subTitle="请确认后端已启动且当前地址可访问。"
            extra={<Button type="primary" onClick={() => void checkBackend()}>重新检测</Button>}
          />
        </Card>
      </main>
    );
  }

  return (
    <main className="auth-gate" aria-label="系统认证">
      <Card className="auth-gate-card">
        <Typography.Title level={2}>解锁系统</Typography.Title>
        <Typography.Paragraph type="secondary">
          API Token 仅保存在当前浏览器会话中，关闭标签页后会自动清除。
        </Typography.Paragraph>
        {!tokenConfigured && (
          <Alert
            type="warning"
            showIcon
            message="后端尚未配置 API Token"
            description="请先在服务端生成 Token，再返回此处验证。"
          />
        )}
        {error && <Alert type="error" showIcon message={error} className="auth-gate-alert" />}
        <Form layout="vertical" onFinish={handleUnlock} requiredMark={false}>
          <Form.Item
            name="token"
            label="API Token"
            rules={[{ required: true, whitespace: true, message: '请输入 API Token' }]}
          >
            <Input.Password autoComplete="current-password" placeholder="请输入 API Token" autoFocus />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            验证并进入
          </Button>
        </Form>
      </Card>
    </main>
  );
}
