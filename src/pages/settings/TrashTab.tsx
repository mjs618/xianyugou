import { useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Popconfirm, Space, Table, message } from 'antd';
import { DeleteOutlined, UndoOutlined } from '@ant-design/icons';
import {
  listTrashedCustomers,
  listTrashedTransactions,
  listTrashedAfterSales,
  restoreCustomer,
  restoreTransaction,
  restoreAfterSales,
  purgeCustomer,
  purgeTransaction,
  purgeAfterSales,
  SOFT_DELETE_RETENTION_DAYS,
} from '@/services/trashService';
import { useAppStore } from '@/store/useAppStore';
import dayjs from 'dayjs';
import type { AfterSales, Customer, Transaction } from '@/types';

/** 回收站 Tab：列出已软删除的客户/交易/售后工单，支持恢复和彻底删除。
 *
 * 状态自包含：trashedCustomers/Transactions/AfterSales + trashLoading。
 * mount effect 加载（替代原容器的 `useEffect([activeTab])`）。
 * restore 操作后调 refreshAll() 刷新全局统计（与原行为一致）；purge 不刷新统计
 * （彻底删除不影响统计指标，因为软删时统计已扣除）。
 */
export default function TrashTab() {
  const { refreshAll } = useAppStore();
  const [trashedCustomers, setTrashedCustomers] = useState<Customer[]>([]);
  const [trashedTransactions, setTrashedTransactions] = useState<Transaction[]>([]);
  const [trashedAfterSales, setTrashedAfterSales] = useState<AfterSales[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);

  const loadTrash = async () => {
    setTrashLoading(true);
    try {
      const [c, t, a] = await Promise.all([
        listTrashedCustomers(),
        listTrashedTransactions(),
        listTrashedAfterSales(),
      ]);
      setTrashedCustomers(c);
      setTrashedTransactions(t);
      setTrashedAfterSales(a);
    } catch (err) {
      console.error('加载回收站失败:', err);
      message.error('加载回收站失败');
    } finally {
      setTrashLoading(false);
    }
  };

  useEffect(() => {
    loadTrash();
  }, []);

  const handleRestoreCustomer = async (id: number) => {
    try {
      await restoreCustomer(id);
      message.success('客户已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  const handleRestoreTransaction = async (id: number) => {
    try {
      await restoreTransaction(id);
      message.success('交易已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  const handleRestoreAfterSales = async (id: number) => {
    try {
      await restoreAfterSales(id);
      message.success('工单已恢复');
      loadTrash();
      refreshAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败');
    }
  };
  const handlePurgeCustomer = async (id: number) => {
    try {
      await purgeCustomer(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };
  const handlePurgeTransaction = async (id: number) => {
    try {
      await purgeTransaction(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };
  const handlePurgeAfterSales = async (id: number) => {
    try {
      await purgeAfterSales(id);
      message.success('已彻底删除');
      loadTrash();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={`回收站说明`}
        description={`删除的客户、交易、售后工单会在此保留 ${SOFT_DELETE_RETENTION_DAYS} 天，期间可随时恢复。超过 ${SOFT_DELETE_RETENTION_DAYS} 天的记录将在应用启动时自动彻底清理。`}
      />
      <Card type="inner" title={`已删除客户（${trashedCustomers.length}）`} size="small">
        <Table
          rowKey="id"
          size="small"
          loading={trashLoading}
          dataSource={trashedCustomers}
          pagination={false}
          locale={{ emptyText: <Empty description="无已删除客户" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '昵称', dataIndex: 'xianyu_nickname' },
            { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            {
              title: '操作', width: 160,
              render: (_: unknown, r: Customer) => (
                <Space size={0}>
                  <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreCustomer(r.id!)}>恢复</Button>
                  <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeCustomer(r.id!)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Card type="inner" title={`已删除交易（${trashedTransactions.length}）`} size="small">
        <Table
          rowKey="id"
          size="small"
          loading={trashLoading}
          dataSource={trashedTransactions}
          pagination={false}
          locale={{ emptyText: <Empty description="无已删除交易" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '商品', dataIndex: 'product_name', ellipsis: true },
            { title: '售价', dataIndex: 'sale_price', width: 90, render: (v: number) => `¥${v}` },
            { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            {
              title: '操作', width: 160,
              render: (_: unknown, r: Transaction) => (
                <Space size={0}>
                  <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreTransaction(r.id!)}>恢复</Button>
                  <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeTransaction(r.id!)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Card type="inner" title={`已删除售后工单（${trashedAfterSales.length}）`} size="small">
        <Table
          rowKey="id"
          size="small"
          loading={trashLoading}
          dataSource={trashedAfterSales}
          pagination={false}
          locale={{ emptyText: <Empty description="无已删除工单" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: '问题描述', dataIndex: 'issue_desc', ellipsis: true },
            { title: '关联交易', dataIndex: 'transaction_id', width: 90 },
            { title: '删除时间', dataIndex: 'deleted_at', width: 160, render: (v: Date) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            {
              title: '操作', width: 160,
              render: (_: unknown, r: AfterSales) => (
                <Space size={0}>
                  <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreAfterSales(r.id!)}>恢复</Button>
                  <Popconfirm title="彻底删除后无法恢复，确认？" okType="danger" onConfirm={() => handlePurgeAfterSales(r.id!)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />}>彻底删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
