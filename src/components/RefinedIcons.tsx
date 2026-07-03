/**
 * 精致矢量图标集 v2
 * - 统一 24x24 视口、1.5 描边宽度、圆角端点
 * - 半透明填充营造层次感
 * - 简洁路径，去除冗余细节
 */

interface IconProps {
  size?: number;
  className?: string;
}

const baseProps = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
});

/** 收入 - 钱袋 + 硬币（硬币半透明填充） */
export function IncomeIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <path d="M9.5 4.5h5l-.4 1.8c2 1 3.4 3.1 3.4 5.7 0 3.6-2.9 6.5-6.5 6.5S4.5 15.6 4.5 12c0-2.6 1.4-4.7 3.4-5.7L9.5 4.5z" />
      <circle cx="12" cy="12" r="2.5" fill="currentColor" fillOpacity={0.12} />
      <path d="M12 10.2v-.4M12 14.2v.4" strokeWidth={1.2} />
    </svg>
  );
}

/** 净利润 - 上升趋势线 + 箭头（底部基线虚化） */
export function ProfitIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <path d="M4 15.5l4.5-4.5 3 3L20 5.5" />
      <path d="M15 5.5h5v5" />
      <path d="M4 19.5h16" strokeWidth={1} opacity={0.35} />
    </svg>
  );
}

/** 交易笔数 - 购物袋（袋身半透明填充） */
export function TradeIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <path
        d="M6 8h12l-1 11c-.1.8-.8 1.5-1.6 1.5H8.6c-.8 0-1.5-.7-1.6-1.5L6 8z"
        fill="currentColor"
        fillOpacity={0.08}
      />
      <path d="M6 8h12l-1 11c-.1.8-.8 1.5-1.6 1.5H8.6c-.8 0-1.5-.7-1.6-1.5L6 8z" />
      <path d="M9 8V6.5C9 4.6 10.3 3 12 3s3 1.6 3 3.5V8" />
    </svg>
  );
}

/** 新客户 - 用户 + 加号徽章（徽章半透明填充） */
export function NewCustomerIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <circle cx="9.5" cy="8" r="3.2" />
      <path d="M3.5 19c0-3.3 2.7-6 6-6 .7 0 1.4.1 2 .3" />
      <circle cx="17" cy="15.5" r="3.5" fill="currentColor" fillOpacity={0.12} />
      <circle cx="17" cy="15.5" r="3.5" />
      <path d="M17 14v3M15.5 15.5h3" strokeWidth={1.3} />
    </svg>
  );
}

/** 质保 - 盾牌 + 对勾（盾牌半透明填充） */
export function WarrantyIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <path
        d="M12 3l7 2.5v5c0 4.5-3 8.3-7 9.5-4-1.2-7-5-7-9.5v-5L12 3z"
        fill="currentColor"
        fillOpacity={0.08}
      />
      <path d="M12 3l7 2.5v5c0 4.5-3 8.3-7 9.5-4-1.2-7-5-7-9.5v-5L12 3z" />
      <path d="M8.5 11.5l2.3 2.3 4.7-4.7" strokeWidth={1.8} />
    </svg>
  );
}

/** 售后 - 齿轮（简洁化，半透明填充） */
export function ToolIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <circle cx="12" cy="12" r="3" fill="currentColor" fillOpacity={0.12} />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" strokeWidth={1.3} />
    </svg>
  );
}

/** 返利 - 礼物盒（盒身半透明填充） */
export function RebateIcon({ size = 20 }: IconProps) {
  return (
    <svg {...baseProps(size)}>
      <path
        d="M4.5 10h15v9c0 .8-.7 1.5-1.5 1.5H6c-.8 0-1.5-.7-1.5-1.5v-9z"
        fill="currentColor"
        fillOpacity={0.08}
      />
      <path d="M4.5 10h15v9c0 .8-.7 1.5-1.5 1.5H6c-.8 0-1.5-.7-1.5-1.5v-9z" />
      <path d="M3 7.5h18V10H3V7.5z" />
      <path d="M12 7.5V20.5" />
      <path d="M12 7.5C12 6 11 4.5 9.5 4.5S7.5 6 8.5 7.5H12zM12 7.5C12 6 13 4.5 14.5 4.5S16.5 6 15.5 7.5H12z" />
    </svg>
  );
}
