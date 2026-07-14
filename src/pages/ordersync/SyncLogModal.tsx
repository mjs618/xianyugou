import { useEffect, useState } from 'react';
import { Empty, Modal, Table, Tag, Typography, message } from 'antd';
import dayjs from 'dayjs';
import { listSyncLogs } from '@/services/xianyuService';
import type { XianyuSyncLog } from '@/types';

const { Text } = Typography;

interface SyncLogModalProps {
  accountId: number | null;
  onClose: () => void;
}

/** 同步日志 Modal：展示某账号的历史同步记录。
 *
 * 状态自包含：syncLogs / logLoading。
 * mount effect（accountId 变化时）加载 listSyncLogs。
 */
export default function SyncLogModal({ accountId, onClose }: SyncLogModalProps) {
  const [syncLogs, setSyncLogs] = useState<XianyuSyncLog[]>([]);
  const [logLoading, setLogLoading] = useState(false);

  useEffect(() => {
    if (accountId !== null) {
      setLogLoading(true);
      listSyncLogs(accountId)
        .then(setSyncLogs)
        .catch(() => message.error('加载同步日志失败'))
        .finally(() => setLogLoading(false));
    }
  }, [accountId]);

  return (
    <Modal
      title="同步日志"
      open={accountId !== null}
      onCancel={onClose}
      footer={null}
      width={720}
    >
      <Table
        rowKey="id"
        size="small"
        loading={logLoading}
        dataSource={syncLogs}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: <Empty description="暂无同步记录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        columns={[
          {
            title: '时间', dataIndex: 'created_at', width: 150,
            render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
          },
          {
            title: '状态', dataIndex: 'status', width: 80,
            render: (v: string) => v === 'success'
              ? <Tag color="green">成功</Tag>
              : <Tag color="red">失败</Tag>,
          },
          { title: '拉取', dataIndex: 'fetched', width: 70, align: 'center' as const },
          { title: '新增', dataIndex: 'created_count', width: 70, align: 'center' as const, render: (v: number) => <Text type="success">{v}</Text> },
          { title: '跳过', dataIndex: 'skipped_count', width: 70, align: 'center' as const },
          {
            title: '错误', dataIndex: 'error', ellipsis: true,
            render: (v?: string) => v ? <Text type="danger" style={{ fontSize: 12 }}>{v}</Text> : '-',
          },
        ]}
      />
    </Modal>
  );
}
