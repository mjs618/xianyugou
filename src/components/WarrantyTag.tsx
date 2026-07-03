import { Tag } from 'antd';
import type { WarrantyStatus } from '@/types';
import { getWarrantyStatus, warrantyTagColor } from '@/utils/warranty';

interface Props {
  warrantyEnd?: Date | string | null;
  status?: string;
}

export default function WarrantyTag({ warrantyEnd, status }: Props) {
  // 交易未完成则不显示质保
  if (status && status !== 'completed') {
    if (status === 'pending') return <Tag color="blue">待发货</Tag>;
    if (status === 'aftersales') return <Tag color="orange">售后中</Tag>;
    if (status === 'closed') return <Tag>已关闭</Tag>;
  }
  const ws: WarrantyStatus = getWarrantyStatus(warrantyEnd);
  return <Tag color={warrantyTagColor(ws.type)}>{ws.label}</Tag>;
}
