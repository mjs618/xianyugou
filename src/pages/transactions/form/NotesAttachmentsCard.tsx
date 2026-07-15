import { Card, Form, Input } from 'antd';
import type { FormInstance } from 'antd';
import AttachmentUpload from '@/components/AttachmentUpload';

const { TextArea } = Input;

interface NotesAttachmentsCardProps {
  form: FormInstance;
}

/** 备注与附件 Card。 */
export default function NotesAttachmentsCard({ form: _form }: NotesAttachmentsCardProps) {
  return (
    <Card type="inner" title="备注与附件" size="small">
      <Form.Item name="notes" label="交易备注">
        <TextArea rows={4} placeholder="添加交易备注..." />
      </Form.Item>
      <Form.Item name="attachments" label="交易附件">
        <AttachmentUpload />
      </Form.Item>
    </Card>
  );
}
