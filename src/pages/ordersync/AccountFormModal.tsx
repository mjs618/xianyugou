import { useEffect, useState } from 'react';
import { Alert, Empty, Form, Input, Modal } from 'antd';
import type { CookieCloudConfigStatus, XianyuAccount } from '@/types';
import type { FormInstance } from 'antd';

const { TextArea } = Input;

interface AccountFormModalProps {
  open: boolean;
  editing: XianyuAccount | null;
  form: FormInstance;
  cookieCloudStatus: CookieCloudConfigStatus | null;
  onCancel: () => void;
  onOk: () => void;
}

/** 添加/编辑账号 Modal：账号备注 + Cookie 文本域。
 *
 * Form 实例由容器传入（与 AccountTable 编辑按钮共享 setFieldsValue 调用）。
 * CookieCloud 状态用于在 Cookie 输入框下方显示不同的 extra 提示。
 */
export default function AccountFormModal({
  open,
  editing,
  form,
  cookieCloudStatus,
  onCancel,
  onOk,
}: AccountFormModalProps) {
  // 静态占位，仅供 lint 满意：state 本身未使用，保留以备未来扩展（如本地草稿）
  const [, setDraft] = useState<string>('');
  useEffect(() => {
    if (!open) setDraft('');
  }, [open]);

  return (
    <Modal
      title={editing ? '更新账号 Cookie' : '添加闲鱼账号'}
      open={open}
      onCancel={onCancel}
      onOk={onOk}
      okText={editing ? '更新' : '添加'}
      width={640}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="nickname" label="账号备注" rules={[{ required: true, message: '请输入账号备注名' }]}>
          <Input placeholder="如：主号 / 副号" />
        </Form.Item>
        <Form.Item
          name="cookies"
          label="闲鱼 Cookie"
          rules={[{ required: true, message: '请粘贴 Cookie' }]}
          extra={
            cookieCloudStatus?.enabled
              ? '粘贴登录闲鱼后复制的完整 Cookie 字符串。Cookie 将加密存储；后续过期时会尝试通过 CookieCloud 自动续 Cookie。'
              : `粘贴登录闲鱼后复制的完整 Cookie 字符串。必须包含 unb（用户ID）和 _m_h5_tk 字段。Cookie 将加密存储；当前 CookieCloud 未启用，过期后需手动更新${cookieCloudStatus?.missing_keys.length ? `（缺少 ${cookieCloudStatus.missing_keys.join('、')}）` : ''}。`
          }
        >
          <TextArea
            rows={6}
            placeholder="在此粘贴 Cookie，格式如：unb=xxxx; _m_h5_tk=xxxx_timestamp; cookie2=xxxx; ..."
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
