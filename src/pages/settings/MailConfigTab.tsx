import { Alert, Button, Col, Form, Input, InputNumber, Row, Typography, message } from 'antd';
import type { FormInstance } from 'antd';
import { updateSettings } from '@/services/settingsService';
import { getErrorMessage, isValidationError } from '@/utils/error';

const { Text } = Typography;

interface MailConfigTabProps {
  /** 容器共享的 mailForm 实例（loadSettings 也会写入此 form）。 */
  form: FormInstance;
  /** 保存成功后调用容器的 loadSettings，回填两个表单（不调 refreshAll，与原行为一致）。 */
  onSaved: () => Promise<void>;
}

/** 邮件配置 Tab：QQ 邮箱 SMTP 配置。
 *
 * Form 实例由容器传入。与 SystemSettingsTab 一样，无自身 state，
 * Tab 切换卸载后重挂载时 Form 会重连实例恢复字段值。
 *
 * 注意：handleSaveMail 不调 refreshAll（原行为如此，邮件配置不影响统计指标）。
 */
export default function MailConfigTab({ form, onSaved }: MailConfigTabProps) {
  const handleSaveMail = async () => {
    try {
      const values = await form.validateFields();
      await updateSettings(values);
      message.success('邮件配置已保存');
      await onSaved();
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      console.error('保存邮件配置失败:', err);
      message.error(getErrorMessage(err, '保存失败'));
    }
  };

  return (
    <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
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
  );
}
