import { useState } from 'react';
import { Card, Table, Tag, Button, Space, Popconfirm, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { formatMoney, formatPercent } from '@/utils/format';
import { formatDate } from '@/utils/date';
import { markPaid, cancelRebate, batchPay } from '@/services/rebateService';
import type { RebateRecord } from '@/types';
import StatCard from '@/components/StatCard';
import { RebateIcon } from '@/components/RefinedIcons';

interface RebatePanelProps {
  rebates: RebateRecord[];
  pendingTotal: number;
  paidTotal: number;
  onReload: () => void;
}

/** 返利结算面板：统计卡片 + 返利表格（含多选批量结算）。
 *
 * 选择状态（selectedRebateKeys）和批量 loading 状态自包含，
 * 仅通过 onReload 回调通知父组件重新加载数据。
 */
export default function RebatePanel({ rebates, pendingTotal, paidTotal, onReload }: RebatePanelProps) {
  const [selectedRebateKeys, setSelectedRebateKeys] = useState<number[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);

  const handleBatchPay = async () => {
    if (selectedRebateKeys.length === 0) return;
    setBatchLoading(true);
    try {
      const result = await batchPay(selectedRebateKeys);
      if (result.skipped > 0) {
        message.warning(`已结算 ${result.updated} 笔，跳过 ${result.skipped} 笔非法状态`);
      } else {
        message.success(`已批量结算 ${result.updated} 笔返利`);
      }
      setSelectedRebateKeys([]);
      onReload();
    } catch {
      message.error('批量结算失败');
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <Card
      title="返利结算"
      extra={
        <Space>
          {selectedRebateKeys.length > 0 && (
            <Popconfirm title={`确认批量结算选中的 ${selectedRebateKeys.length} 笔返利？`} onConfirm={handleBatchPay}>
              <Button type="primary" loading={batchLoading}>批量结算（{selectedRebateKeys.length}）</Button>
            </Popconfirm>
          )}
          <span style={{ color: 'var(--color-text-secondary)' }}>待结算 {pendingTotal} 元</span>
        </Space>
      }
    >
      <Table
        rowKey="id"
        dataSource={rebates}
        size="small"
        pagination={{ pageSize: 10 }}
        rowSelection={{
          selectedRowKeys: selectedRebateKeys,
          onChange: (keys) => setSelectedRebateKeys(keys as number[]),
          getCheckboxProps: (r: RebateRecord) => ({ disabled: r.status !== 'pending' }),
        }}
        columns={[
          { title: '介绍人ID', dataIndex: 'referrer_id', width: 90 },
          { title: '买家ID', dataIndex: 'buyer_id', width: 90 },
          { title: '返利金额', dataIndex: 'amount', width: 100, render: (v: number) => <span style={{ color: 'var(--theme-primary)', fontWeight: 600 }}>{formatMoney(v)}</span>, align: 'right' as const },
          { title: '比例', dataIndex: 'rate', width: 70, render: (v: number) => `${Math.round(v * 100)}%`, align: 'center' as const },
          { title: '状态', dataIndex: 'status', width: 90, render: (s: string) => {
            const map: Record<string, { label: string; color: string }> = { pending: { label: '待结算', color: 'orange' }, paid: { label: '已支付', color: 'green' }, cancelled: { label: '已取消', color: 'default' } };
            return <Tag color={map[s]?.color ?? 'default'}>{map[s]?.label ?? s}</Tag>;
          }},
          { title: '创建时间', dataIndex: 'created_at', width: 140, render: (v: Date) => formatDate(v) },
          { title: '支付时间', dataIndex: 'paid_at', width: 140, render: (v?: Date) => v ? formatDate(v) : '-' },
          { title: '操作', width: 140, render: (_: unknown, r: RebateRecord) => (
            <Space size={4}>
              {r.status === 'pending' && (
                <>
                  <Popconfirm title="确认标记为已支付？" onConfirm={async () => { await markPaid(r.id!); message.success('已标记为已支付'); onReload(); }}>
                    <Button size="small" type="primary">结算</Button>
                  </Popconfirm>
                  <Popconfirm title="确认取消该返利？" onConfirm={async () => { await cancelRebate(r.id!); message.success('已取消'); onReload(); }}>
                    <Button size="small" danger>取消</Button>
                  </Popconfirm>
                </>
              )}
            </Space>
          )},
        ]}
      />
    </Card>
  );
}

/** 返利统计卡片（3 个 StatCard）。
 * 独立导出以便父组件在返利表格上方布局。
 */
export function RebateStats({ rebates, pendingTotal, paidTotal }: { rebates: RebateRecord[]; pendingTotal: number; paidTotal: number }) {
  return (
    <Card title="返利支出统计">
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <StatCard title="累计返利" value={paidTotal} prefix="¥" icon={<RebateIcon />} color="var(--color-success)" />
          </div>
          <div style={{ flex: 1 }}>
            <StatCard title="待结算" value={pendingTotal} prefix="¥" icon={<RebateIcon />} color="var(--theme-primary)" />
          </div>
          <div style={{ flex: 1 }}>
            <StatCard title="返利笔数" value={rebates.length} precision={0} prefix="" icon={<RebateIcon />} color="var(--color-info)" />
          </div>
        </div>
      </Space>
    </Card>
  );
}
