import { Card, Statistic } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface StatCardProps {
  title: string;
  value: number;
  precision?: number;
  prefix?: string;
  suffix?: string;
  change?: number; // 环比变化比例
  icon?: ReactNode;
  color?: string;
  to?: string;
}

export default function StatCard({ title, value, precision = 2, prefix = '¥', suffix, change, icon, color = 'var(--theme-primary)', to }: StatCardProps) {
  const showChange = change !== undefined;
  const isUp = (change ?? 0) >= 0;
  const card = (
      <Card className="stat-card" hoverable={!!to} bodyStyle={{ padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ color: 'var(--color-text-secondary)', fontSize: 13, marginBottom: 8, letterSpacing: 0.2 }}>{title}</div>
            <Statistic
              value={value}
              precision={precision}
              prefix={prefix}
              suffix={suffix}
              valueStyle={{ color: 'var(--color-dark)', fontSize: 26, fontWeight: 600, lineHeight: 1.2 }}
            />
            {showChange && (
              <div style={{ marginTop: 10, fontSize: 12, color: isUp ? 'var(--color-success)' : 'var(--color-danger)' }}>
                {change === 0 ? (
                  <span style={{ color: 'var(--color-text-secondary)' }}>持平</span>
                ) : (
                  <>
                    {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(change * 100).toFixed(1)}%
                    <span style={{ color: 'var(--color-text-tertiary)', marginLeft: 4 }}>环比</span>
                  </>
                )}
              </div>
            )}
          </div>
          {icon && (
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: `linear-gradient(135deg, ${color}12 0%, ${color}1f 100%)`,
                color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: `1px solid ${color}1a`,
                boxShadow: `inset 0 1px 0 ${color}14`,
              }}
            >
              {icon}
            </div>
          )}
        </div>
      </Card>
  );
  if (!to) return card;
  return <Link to={to} className="stat-card-link" aria-label={`${title}，查看详情`}>{card}</Link>;
}
