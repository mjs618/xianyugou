import { Card, Tag } from 'antd';

interface TopIssuesCardProps {
  issues: { productName: string; count: number }[];
}

/** 高频问题商品 TOP5 列表。 */
export default function TopIssuesCard({ issues }: TopIssuesCardProps) {
  if (issues.length === 0) return null;
  return (
    <Card title="高频问题商品 TOP5" style={{ marginTop: 16 }}>
      {issues.map((i, idx) => (
        <div key={i.productName} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--color-border)' }}>
          <span>{idx + 1}. {i.productName}</span>
          <Tag color="orange">{i.count} 次</Tag>
        </div>
      ))}
    </Card>
  );
}
