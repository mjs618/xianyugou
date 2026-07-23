import { useEffect, useState } from 'react';
import { Alert, Button, Empty, Modal, Segmented, Space, Table, Tag, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  listItems,
  summarizeXianyuItems,
  filterXianyuItemsByTemplateProjection,
} from '@/services/xianyuService';
import type { XianyuItemTemplateProjectionFilter } from '@/services/xianyuService';
import ProductImage from '@/components/ProductImage';
import type { XianyuItem } from '@/types';

const { Text } = Typography;

interface ItemMirrorModalProps {
  accountId: number | null;
  /** 同步商品按钮的 loading 状态（与容器 itemSyncingId 一致） */
  syncing: boolean;
  /** 点击「同步商品」按钮时回调 */
  onSync: (id: number) => void;
  onClose: () => void;
}

/** 商品镜像 Modal：展示某账号的闲鱼商品镜像，支持模板投影筛选。
 *
 * 状态自包含：itemMirrors / itemLoading / itemTemplateFilter。
 * mount effect（accountId 变化时）加载 listItems。
 * 「同步商品」按钮调容器 onSync（触发同步 + 完成后容器重新打开本 Modal 刷新）。
 */
export default function ItemMirrorModal({ accountId, syncing, onSync, onClose }: ItemMirrorModalProps) {
  const [itemMirrors, setItemMirrors] = useState<XianyuItem[]>([]);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemTemplateFilter, setItemTemplateFilter] = useState<XianyuItemTemplateProjectionFilter>('all');

  useEffect(() => {
    if (accountId !== null) {
      setItemLoading(true);
      listItems(accountId)
        .then(setItemMirrors)
        .catch(() => message.error('加载商品镜像失败'))
        .finally(() => setItemLoading(false));
    }
  }, [accountId]);

  const itemSummary = summarizeXianyuItems(itemMirrors);
  const filteredItemMirrors = filterXianyuItemsByTemplateProjection(itemMirrors, itemTemplateFilter);

  return (
    <Modal
      title="商品镜像"
      open={accountId !== null}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>关闭</Button>,
        <Button
          key="sync"
          type="primary"
          icon={<ReloadOutlined />}
          loading={accountId !== null && syncing}
          disabled={accountId === null}
          onClick={() => accountId !== null && onSync(accountId)}
        >
          同步商品
        </Button>,
      ]}
      width={900}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="这里展示的是闲鱼商品镜像摘要"
        description={`共 ${itemSummary.total} 个商品 · 已导入模板 ${itemSummary.imported} 个 · 未导入 ${itemSummary.unimported} 个。导入商品模板请到「设置 -> 商品模板 -> 从闲鱼导入商品」。`}
      />
      <Segmented
        size="small"
        value={itemTemplateFilter}
        onChange={(value) => setItemTemplateFilter(value as XianyuItemTemplateProjectionFilter)}
        options={[
          { label: '全部', value: 'all' },
          { label: '已导入模板', value: 'imported' },
          { label: '未导入模板', value: 'unimported' },
        ]}
        style={{ marginBottom: 12 }}
      />
      <Table
        rowKey="id"
        size="small"
        loading={itemLoading}
        dataSource={filteredItemMirrors}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: <Empty description="暂无商品镜像，请先点击「同步商品」" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        columns={[
          {
            title: '商品',
            dataIndex: 'title',
            ellipsis: true,
            render: (v?: string, record?: any) => (
              <Space>
                <ProductImage url={record?.image_url} size={32} showFallback={false} />
                <span>{v || '-'}</span>
              </Space>
            ),
          },
          {
            title: '状态',
            dataIndex: 'item_status',
            width: 100,
            render: (v?: string) => v ? <Tag>{v}</Tag> : '-',
          },
          {
            title: '模板',
            dataIndex: 'projected_template_id',
            width: 90,
            render: (v?: number) => v ? <Tag color="green">已导入</Tag> : <Tag>未导入</Tag>,
          },
          {
            title: '价格',
            dataIndex: 'price',
            width: 90,
            align: 'right' as const,
            render: (v: number) => `￥${Number(v || 0).toFixed(2)}`,
          },
          {
            title: '闲鱼商品ID',
            dataIndex: 'item_id',
            width: 150,
            render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text>,
          },
          {
            title: '最近同步',
            dataIndex: 'last_seen_at',
            width: 150,
            render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
          },
        ]}
      />
    </Modal>
  );
}
