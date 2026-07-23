import { Modal, Select, Input } from 'antd';
import AttachmentUpload from '@/components/AttachmentUpload';
import { formatDateTime } from '@/utils/date';
import type { Transaction } from '@/types';

const { TextArea } = Input;

interface CreateAfterSalesFormState {
  transaction_id: number | undefined;
  issue_desc: string;
  attachments: string[];
}

interface CreateAfterSalesModalProps {
  open: boolean;
  form: CreateAfterSalesFormState;
  transactions: Map<number, Transaction>;
  onCancel: () => void;
  onChange: (form: CreateAfterSalesFormState) => void;
  onOk: () => void;
}

/** 创建售后工单 Modal：选择关联交易 + 问题描述 + 附件上传。 */
export default function CreateAfterSalesModal({
  open,
  form,
  transactions,
  onCancel,
  onChange,
  onOk,
}: CreateAfterSalesModalProps) {
  return (
    <Modal title="创建售后工单" open={open} onCancel={onCancel} onOk={onOk} okText="创建">
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 4 }}>关联交易</div>
        <Select
          style={{ width: '100%' }}
          placeholder="选择交易"
          value={form.transaction_id}
          onChange={(v) => onChange({ ...form, transaction_id: v })}
          showSearch
          filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
          options={Array.from(transactions.values()).map((t) => ({ value: t.id, label: `${t.product_name} - ${formatDateTime(t.trade_at)}` }))}
        />
      </div>
      <div>
        <div style={{ marginBottom: 4 }}>问题描述</div>
        <TextArea rows={4} value={form.issue_desc} onChange={(e) => onChange({ ...form, issue_desc: e.target.value })} placeholder="描述客户反馈的问题" />
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ marginBottom: 4 }}>问题截图/附件</div>
        <AttachmentUpload
          value={form.attachments}
          onChange={(ids) => onChange({ ...form, attachments: ids })}
          maxCount={6}
        />
      </div>
    </Modal>
  );
}
