import { useEffect, useState } from 'react';
import { Alert, Empty, Modal, Segmented, Table, Tag, Typography, message } from 'antd';
import dayjs from 'dayjs';
import {
  listOrders,
  summarizeXianyuOrders,
  filterXianyuOrdersByProjection,
  formatXianyuOrderProjectionSummary,
} from '@/services/xianyuService';
import type { XianyuOrderProjectionFilter } from '@/services/xianyuService';
import type { XianyuOrder } from '@/types';

const { Text } = Typography;

interface OrderMirrorModalProps {
  accountId: number | null;
  onClose: () => void;
}

/** 订单镜像 Modal：展示某账号的闲鱼订单镜像，支持投影筛选。
 *
 * 状态自包含：mirrorOrders / orderLoading / orderProjectionFilter。
 * mount effect（accountId 变化时）加载 listOrders。
 * 关闭由父组件控制（onClose 置 accountId=null）。
 */
export default function OrderMirrorModal({ accountId, onClose }: OrderMirrorModalProps) {
  const [mirrorOrders, setMirrorOrders] = useState<XianyuOrder[]>([]);
  const [orderLoading, setOrderLoading] = useState(false);
  const [orderProjectionFilter, setOrderProjectionFilter] = useState<XianyuOrderProjectionFilter>('all');

  useEffect(() => {
    if (accountId !== null) {
      setOrderLoading(true);
      listOrders(accountId)
        .then(setMirrorOrders)
        .catch(() => message.error('加载订单镜像失败'))
        .finally(() => setOrderLoading(false));
    }
  }, [accountId]);

  const mirrorSummary = summarizeXianyuOrders(mirrorOrders);
  const filteredMirrorOrders = filterXianyuOrdersByProjection(mirrorOrders, orderProjectionFilter);

  return (
    <Modal
      title="订单镜像"
      open={accountId !== null}
      onCancel={onClose}
      footer={null}
      width={900}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        description={formatXianyuOrderProjectionSummary(mirrorSummary)}
        message="这里展示的是闲鱼订单镜像摘要，不包含平台原始响应 raw_order。"
      />
      <Segmented
        size="small"
        value={orderProjectionFilter}
        onChange={(value) => setOrderProjectionFilter(value as XianyuOrderProjectionFilter)}
        options={[
          { label: '全部', value: 'all' },
          { label: '已生成交易', value: 'projected' },
          { label: '未生成交易', value: 'unprojected' },
        ]}
        style={{ marginBottom: 12 }}
      />
      <Table
        rowKey="id"
        size="small"
        loading={orderLoading}
        dataSource={filteredMirrorOrders}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: <Empty description="暂无订单镜像" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        columns={[
          {
            title: '订单号', dataIndex: 'order_no', width: 150,
            render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
          },
          { title: '买家', dataIndex: 'buyer_nick', width: 120, render: (v?: string) => v || '-' },
          { title: '商品', dataIndex: 'product_name', ellipsis: true, render: (v?: string) => v || '-' },
          {
            title: '状态', dataIndex: 'order_status', width: 110,
            render: (v?: string) => v ? <Tag>{v}</Tag> : '-',
          },
          {
            title: '投影', dataIndex: 'projected_transaction_id', width: 90,
            render: (v?: number) => v
              ? <Tag color="green">已生成</Tag>
              : <Tag>未生成</Tag>,
          },
          {
            title: '金额', dataIndex: 'sale_price', width: 90, align: 'right' as const,
            render: (v: number) => `¥${Number(v || 0).toFixed(2)}`,
          },
          {
            title: '交易时间', dataIndex: 'trade_at', width: 150,
            render: (v?: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
          },
          {
            title: '最近同步', dataIndex: 'last_seen_at', width: 150,
            render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
          },
        ]}
      />
    </Modal>
  );
}
