import { Card, Col, Row, List, Button } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import WarrantyTag from '@/components/WarrantyTag';
import { formatDate } from '@/utils/date';
import type { Transaction } from '@/types';

interface UrgentWarrantyTradesProps {
  trades: Transaction[];
  onNavigate: (path: string) => void;
}

/** Dashboard：质保即将到期交易（条件渲染）。 */
export default function UrgentWarrantyTrades({ trades, onNavigate }: UrgentWarrantyTradesProps) {
  if (trades.length === 0) return null;
  return (
    <Card title={<span><WarningOutlined style={{ color: 'var(--color-danger)', marginRight: 8 }} />质保即将到期交易</span>} style={{ marginTop: 16 }}>
      <List
        dataSource={trades.slice(0, 5)}
        renderItem={(t) => (
          <List.Item
            actions={[<Button type="link" size="small" onClick={() => onNavigate(`/transactions/${t.id}`)}>详情</Button>]}
          >
            <List.Item.Meta
              title={t.product_name}
              description={
                <span style={{ fontSize: 12 }}>
                  到期: {formatDate(t.warranty_end, 'YYYY-MM-DD HH:mm')} <WarrantyTag warrantyEnd={t.warranty_end} status={t.status} />
                </span>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  );
}
