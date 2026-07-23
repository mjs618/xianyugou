import { Modal, Select, Input } from 'antd';
import type { SolutionType } from '@/types';
import { solutionMap } from './constants';

const { TextArea } = Input;

interface ResolveFormState {
  type?: SolutionType;
  desc: string;
}

interface ResolveAfterSalesModalProps {
  open: boolean;
  form: ResolveFormState;
  onCancel: () => void;
  onChange: (form: ResolveFormState) => void;
  onOk: () => void;
}

/** 标记为已解决 Modal：选择解决方式 + 选填说明。 */
export default function ResolveAfterSalesModal({
  open,
  form,
  onCancel,
  onChange,
  onOk,
}: ResolveAfterSalesModalProps) {
  return (
    <Modal title="标记为已解决" open={open} onCancel={onCancel} onOk={onOk} okText="确认解决">
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 4 }}>解决方式</div>
        <Select
          style={{ width: '100%' }}
          placeholder="选择解决方式"
          value={form.type}
          onChange={(v) => onChange({ ...form, type: v })}
          options={(Object.keys(solutionMap) as SolutionType[]).map((k) => ({ value: k, label: solutionMap[k] }))}
        />
      </div>
      <div>
        <div style={{ marginBottom: 4 }}>解决说明</div>
        <TextArea rows={3} value={form.desc} onChange={(e) => onChange({ ...form, desc: e.target.value })} placeholder="选填" />
      </div>
    </Modal>
  );
}

export type { ResolveFormState };
