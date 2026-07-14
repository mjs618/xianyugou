// 销售渠道中文标签（xianyu/wechat/other → 闲鱼/微信/其他）
export const channelLabel = (channel: string): string => {
  const map: Record<string, string> = { xianyu: '闲鱼', wechat: '微信', other: '其他' };
  return map[channel] || channel;
};

// 渠道标签颜色（闲鱼=蓝/微信=绿/其他=灰），供 Tag 组件 color 属性使用
export const channelColorMap: Record<string, string> = {
  xianyu: 'blue',
  wechat: 'green',
  other: 'default',
};

// 金额格式化
export const formatMoney = (value: number, withSymbol = true): string => {
  const fixed = Number.isFinite(value) ? value : 0;
  const str = fixed.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return withSymbol ? `¥${str}` : str;
};

// 紧凑金额（万、亿）
export const formatMoneyCompact = (value: number): string => {
  if (!Number.isFinite(value)) return '¥0';
  if (Math.abs(value) >= 100000000) return `¥${(value / 100000000).toFixed(2)}亿`;
  if (Math.abs(value) >= 10000) return `¥${(value / 10000).toFixed(2)}万`;
  return formatMoney(value);
};

// 百分比
export const formatPercent = (value: number, digits = 1): string => {
  if (!Number.isFinite(value)) return '0%';
  return `${(value * 100).toFixed(digits)}%`;
};

// 环比变化箭头
export const formatChange = (current: number, prev: number): { text: string; up: boolean; zero: boolean } => {
  if (prev === 0) {
    return { text: current > 0 ? '新增' : '持平', up: current > 0, zero: current === 0 };
  }
  const change = (current - prev) / Math.abs(prev);
  const up = change >= 0;
  return { text: `${up ? '↑' : '↓'} ${formatPercent(Math.abs(change))}`, up, zero: false };
};
