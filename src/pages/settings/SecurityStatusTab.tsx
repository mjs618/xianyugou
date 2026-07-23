import { Card, Space, Descriptions, Tag, Alert } from 'antd';
import { SafetyOutlined } from '@ant-design/icons';

/** 安全状态 Tab：纯静态展示敏感字段加密说明与数据安全建议。无状态。 */
export default function SecurityStatusTab() {
  return (
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
  );
}
