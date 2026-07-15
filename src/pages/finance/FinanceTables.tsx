import { Card, Table, Tag, Button, Popconfirm, message, Empty } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { formatMoney, formatPercent } from '@/utils/format';
import { formatDate } from '@/utils/date';
import { deleteExpense } from '@/services/expenseService';
import type { ProductProfitStat, CustomerValueStat, OperatingExpense } from '@/types';

interface FinanceTablesProps {
  products: ProductProfitStat[];
  customers: CustomerValueStat[];
  expenses: OperatingExpense[];
  onReload: () => void;
  onAddExpense: () => void;
}

/** 商品利润排行 + 客户消费排行 + 运营支出明细表格。
 *
 * 排行表格纯渲染（数据由父组件传入），支出表格含删除操作（通过 onReload 回调）。
 */
export default function FinanceTables({ products, customers, expenses, onReload, onAddExpense }: FinanceTablesProps) {
  const emptyText = <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  return (
    <>
      {/* 商品利润排行 + 客户消费排行 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 16, marginTop: 16 }}>
        <Card title="商品利润排行">
          <Table
            rowKey="productName"
            dataSource={products}
            size="small"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText }}
            columns={[
              { title: '商品', dataIndex: 'productName', ellipsis: true },
              { title: '笔数', dataIndex: 'count', width: 60, align: 'center' as const },
              { title: '收入', dataIndex: 'totalIncome', width: 100, render: (v: number) => formatMoney(v), align: 'right' as const },
              { title: '成本', dataIndex: 'totalCost', width: 100, render: (v: number) => formatMoney(v), align: 'right' as const },
              { title: '利润', dataIndex: 'totalProfit', width: 100, render: (v: number) => <span style={{ color: 'var(--color-success)' }}>{formatMoney(v)}</span>, align: 'right' as const },
              { title: '利润率', dataIndex: 'profitRate', width: 80, render: (v: number) => formatPercent(v), align: 'right' as const },
            ]}
          />
        </Card>
        <Card title="客户消费排行">
          <Table
            rowKey="customerId"
            dataSource={customers}
            size="small"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText }}
            columns={[
              { title: '客户', dataIndex: 'nickname', ellipsis: true },
              { title: '笔数', dataIndex: 'tradeCount', width: 60, align: 'center' as const },
              { title: '累计消费', dataIndex: 'totalSpent', width: 120, render: (v: number) => formatMoney(v), align: 'right' as const },
              {
                title: '等级',
                dataIndex: 'level',
                width: 70,
                render: (l: string) => l === 'core' ? '核心' : l === 'vip' ? 'VIP' : '普通',
              },
            ]}
          />
        </Card>
      </div>

      {/* 运营支出明细 */}
      <Card
        title="运营支出明细"
        style={{ marginTop: 16 }}
        extra={<Button size="small" icon={<PlusOutlined />} onClick={onAddExpense}>新增支出</Button>}
      >
        <Table
          rowKey="id"
          dataSource={expenses}
          size="small"
          pagination={{ pageSize: 8 }}
          locale={{ emptyText }}
          className="expense-detail-table"
          scroll={{ x: 700 }}
          columns={[
            { title: '类型', dataIndex: 'category', width: 120, render: (v: string) => <Tag color={v === '擦亮' ? 'orange' : 'default'}>{v}</Tag> },
            { title: '金额', dataIndex: 'amount', width: 120, render: (v: number) => <span style={{ color: 'var(--color-danger)', fontWeight: 600 }}>{formatMoney(v)}</span>, align: 'right' as const },
            { title: '发生时间', dataIndex: 'occurred_at', width: 160, render: (v: Date) => formatDate(v) },
            { title: '备注', dataIndex: 'notes', width: 200, ellipsis: true, render: (v?: string) => v || '-' },
            {
              title: '操作',
              width: 80,
              render: (_: unknown, r: OperatingExpense) => (
                <Popconfirm
                  title="确认删除这笔支出？"
                  onConfirm={async () => {
                    await deleteExpense(r.id);
                    message.success('已删除');
                    onReload();
                  }}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
    </>
  );
}
