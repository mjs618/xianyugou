import { Card } from 'antd';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

type Variant = 'danger' | 'warning' | 'success';

const palette: Record<Variant, { light: string; border: string; color: string }> = {
  danger: { light: 'var(--color-danger-light)', border: 'var(--color-danger-border)', color: 'var(--color-danger)' },
  warning: { light: 'var(--color-warning-light)', border: 'var(--color-warning-border)', color: 'var(--theme-primary)' },
  success: { light: 'var(--color-success-light)', border: 'var(--color-success-border)', color: 'var(--color-success)' },
};

interface AlertStatCardProps {
  icon: ReactNode;
  label: string;
  value: number | string;
  variant: Variant;
  to: string;
}

/** 仪表盘告警统计卡（质保到期/待处理售后/待结算返利 共用样式）。 */
export default function AlertStatCard({ icon, label, value, variant, to }: AlertStatCardProps) {
  const p = palette[variant];
  return (
    <Link to={to} className="stat-card-link" aria-label={`${label}，查看详情`}>
      <Card hoverable>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: `linear-gradient(135deg, ${p.light} 0%, ${p.border} 100%)`,
            color: p.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: `1px solid ${p.border}`,
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.5)',
          }}>
            {icon}
          </div>
          <div>
            <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: p.color, lineHeight: 1.2 }} className="tabular-nums">{value}</div>
          </div>
        </div>
      </Card>
    </Link>
  );
}
