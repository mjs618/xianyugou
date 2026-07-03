import { useMemo } from 'react';
import { useThemeStore } from '@/store/useThemeStore';

/**
 * Recharts 图表颜色配置（深色模式适配）
 *
 * SVG 属性（stroke/fill/stopColor）不支持 CSS var()，需通过 JS 动态绑定字符串值。
 * 此 hook 根据当前主题的 isDark 标志返回适配深浅两套配色的颜色对象，供 Dashboard、
 * FinanceReport 等图表页面共用，避免颜色配置散落多处。
 */
export interface ChartColors {
  /** 收入系列（橙色） */
  income: string;
  /** 利润系列（绿色） */
  profit: string;
  /** 成本系列（灰色） */
  cost: string;
  /** 危险/退款系列（红色） */
  danger: string;
  /** 警告系列（黄色） */
  warning: string;
  /** 网格线 */
  grid: string;
  /** 坐标轴文本 */
  axisText: string;
  /** 坐标轴线 */
  axisLine: string;
  /** Tooltip 背景 */
  tooltipBg: string;
  /** Tooltip 文本 */
  tooltipText: string;
  /** Tooltip 边框 */
  tooltipBorder: string;
  /** 饼图色板（4 色） */
  pieColors: string[];
}

/** 根据是否深色模式返回图表颜色配置 */
export function getChartColors(isDark: boolean): ChartColors {
  return isDark
    ? {
        income: '#fd7e14',
        profit: '#20c997',
        cost: '#adb5bd',
        danger: '#ff6b6b',
        warning: '#ffa94d',
        grid: '#2f3033',
        axisText: '#909296',
        axisLine: '#2f3033',
        tooltipBg: '#1f2024',
        tooltipText: '#e9ecef',
        tooltipBorder: '#2f3033',
        pieColors: ['#fd7e14', '#20c997', '#ff6b6b', '#ffa94d'],
      }
    : {
        income: '#e8590c',
        profit: '#099268',
        cost: '#868e96',
        danger: '#e03131',
        warning: '#f59f00',
        grid: '#f1f3f5',
        axisText: '#868e96',
        axisLine: '#e9ecef',
        tooltipBg: '#ffffff',
        tooltipText: '#1f2937',
        tooltipBorder: '#e9ecef',
        pieColors: ['#e8590c', '#099268', '#e03131', '#f59f00'],
      };
}

/** 图表颜色 Hook：根据当前主题自动返回适配深浅模式的颜色配置 */
export function useChartColors(): ChartColors {
  const isDark = useThemeStore((s) => s.theme.isDark === true);
  return useMemo(() => getChartColors(isDark), [isDark]);
}
