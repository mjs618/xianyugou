/**
 * 主题配置文件
 * 定义所有主题预设，支持一键换肤
 * 新增主题只需在 themes 数组中添加一个预设对象
 */

/** 主题颜色定义 */
export interface ThemeColors {
  /** 主题色（按钮、链接、选中态） */
  primary: string;
  /** 主题色悬浮态 */
  primaryHover: string;
  /** 主题色浅色（选中背景、未读标记） */
  primaryLight: string;
  /** 主题色极浅背景（卡片渐变、列表悬浮） */
  primaryBg: string;
  /** 主题色边框 */
  primaryBorder: string;
  /** 主题色阴影 RGB（用于 rgba 阴影） */
  primaryShadowRgb: string;
}

/** 主题预设 */
export interface ThemePreset {
  /** 唯一标识 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 预览色块（用于切换器展示） */
  swatch: string;
  /** 颜色配置 */
  colors: ThemeColors;
  /** 是否为深色模式主题（影响 data-theme 属性与 Ant Design token） */
  isDark?: boolean;
}

/** 内置主题预设列表 */
export const themes: ThemePreset[] = [
  {
    id: 'xianyu-orange',
    name: '闲鱼橙',
    swatch: '#e8590c',
    colors: {
      primary: '#e8590c',
      primaryHover: '#d9480f',
      primaryLight: '#fff4e6',
      primaryBg: '#fffaf5',
      primaryBorder: '#ffe8cc',
      primaryShadowRgb: '232, 89, 12',
    },
  },
  {
    id: 'ocean-blue',
    name: '海洋蓝',
    swatch: '#1971c2',
    colors: {
      primary: '#1971c2',
      primaryHover: '#1864ab',
      primaryLight: '#e7f5ff',
      primaryBg: '#f1f8ff',
      primaryBorder: '#d0ebff',
      primaryShadowRgb: '25, 113, 194',
    },
  },
  {
    id: 'emerald-green',
    name: '翠绿',
    swatch: '#099268',
    colors: {
      primary: '#099268',
      primaryHover: '#087f5b',
      primaryLight: '#e6fcf5',
      primaryBg: '#f0faf6',
      primaryBorder: '#c3fae8',
      primaryShadowRgb: '9, 146, 104',
    },
  },
  {
    id: 'cherry-pink',
    name: '樱花粉',
    swatch: '#c2255c',
    colors: {
      primary: '#c2255c',
      primaryHover: '#a61e4d',
      primaryLight: '#fff0f6',
      primaryBg: '#fff5f9',
      primaryBorder: '#ffdeeb',
      primaryShadowRgb: '194, 37, 92',
    },
  },
  {
    id: 'midnight-purple',
    name: '暗夜紫',
    swatch: '#5f3dc4',
    colors: {
      primary: '#5f3dc4',
      primaryHover: '#4c2db5',
      primaryLight: '#f3f0ff',
      primaryBg: '#f8f6ff',
      primaryBorder: '#e5dbff',
      primaryShadowRgb: '95, 61, 196',
    },
  },
  {
    id: 'dark',
    name: '深色模式',
    swatch: '#fd7e14',
    isDark: true,
    colors: {
      // 主题色提亮一档，在深色背景上更醒目
      primary: '#fd7e14',
      primaryHover: '#f76707',
      // 浅色变体改为深色透明版（用于选中态背景）
      primaryLight: '#2a2a30',
      primaryBg: '#232428',
      primaryBorder: '#3a3b40',
      primaryShadowRgb: '253, 126, 20',
    },
  },
];

/** 默认主题 ID */
export const DEFAULT_THEME_ID = 'xianyu-orange';

/** 根据 ID 获取主题预设 */
export function getThemeById(id: string): ThemePreset {
  return themes.find((t) => t.id === id) || themes[0];
}

/**
 * 将主题颜色应用为 CSS 自定义属性到 :root
 * 同时根据 isDark 设置 data-theme 属性，触发 CSS 中 [data-theme="dark"] 覆盖
 */
export function applyThemeToCSS(preset: ThemePreset): void {
  const { colors, isDark } = preset;
  const root = document.documentElement;
  root.style.setProperty('--theme-primary', colors.primary);
  root.style.setProperty('--theme-primary-hover', colors.primaryHover);
  root.style.setProperty('--theme-primary-light', colors.primaryLight);
  root.style.setProperty('--theme-primary-bg', colors.primaryBg);
  root.style.setProperty('--theme-primary-border', colors.primaryBorder);
  root.style.setProperty('--theme-primary-shadow-rgb', colors.primaryShadowRgb);
  // 设置 data-theme 属性，CSS [data-theme="dark"] 选择器将覆盖通用色与语义色
  root.setAttribute('data-theme', isDark ? 'dark' : 'light');
}

/**
 * 生成 Ant Design ConfigProvider 所需的 theme 配置
 * 深色模式下注入 dark token，确保 antd 组件背景/文本/边框与深色主题一致
 */
export function getAntdThemeConfig(preset: ThemePreset) {
  const isDark = preset.isDark === true;
  const { colors } = preset;
  return {
    token: {
      colorPrimary: colors.primary,
      borderRadius: 6,
      fontFamily: "'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
      fontSize: 14,
      controlHeight: 32,
      ...(isDark
        ? {
            colorBgContainer: '#1f2024',
            colorBgElevated: '#26272b',
            colorBgLayout: '#1a1b1e',
            colorText: '#e9ecef',
            colorTextSecondary: '#909296',
            colorTextTertiary: '#5c5f66',
            colorTextQuaternary: '#3a3b40',
            colorBorder: '#2f3033',
            colorBorderSecondary: '#25262b',
            colorBgBlur: '#1f2024',
          }
        : {}),
    },
    components: {
      Menu: {
        itemSelectedColor: colors.primary,
        itemSelectedBg: colors.primaryLight,
        ...(isDark ? { itemBg: '#1f2024', subMenuItemBg: '#1f2024' } : {}),
      },
      Card: {
        headerFontSize: 15,
        headerHeight: 48,
        ...(isDark ? { colorBgContainer: '#1f2024' } : {}),
      },
      ...(isDark
        ? {
            Layout: { headerBg: '#1f2024', bodyBg: '#1a1b1e', siderBg: '#1f2024' },
            Table: { headerBg: '#26272b', rowHoverBg: '#26272b', borderColor: '#2f3033' },
            Modal: { contentBg: '#1f2024', headerBg: '#1f2024' },
            Input: { colorBgContainer: '#26272b' },
            InputNumber: { colorBgContainer: '#26272b' },
            Select: { colorBgContainer: '#26272b', optionSelectedBg: '#2a2a30' },
            DatePicker: { colorBgContainer: '#26272b' },
            Drawer: { colorBgElevated: '#1f2024' },
            Tabs: { itemActiveColor: colors.primary, inkBarColor: colors.primary },
            Tooltip: { colorBgSpotlight: '#3a3b40' },
            Popover: { colorBgSpotlight: '#3a3b40' },
            Dropdown: { colorBgElevated: '#1f2024' },
          }
        : {}),
    },
  };
}
