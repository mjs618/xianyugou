import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  DEFAULT_THEME_ID,
  getThemeById,
  applyThemeToCSS,
  getAntdThemeConfig,
  type ThemePreset,
  type ThemeColors,
} from '@/config/themes';

interface ThemeState {
  /** 当前主题 ID */
  themeId: string;
  /** 当前主题预设 */
  theme: ThemePreset;
  /** 当前主题颜色 */
  colors: ThemeColors;
  /** Ant Design 主题配置 */
  antdTheme: ReturnType<typeof getAntdThemeConfig>;
  /** 切换主题 */
  setTheme: (id: string) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      themeId: DEFAULT_THEME_ID,
      theme: getThemeById(DEFAULT_THEME_ID),
      colors: getThemeById(DEFAULT_THEME_ID).colors,
      antdTheme: getAntdThemeConfig(getThemeById(DEFAULT_THEME_ID)),

      setTheme: (id: string) => {
        const theme = getThemeById(id);
        // 应用 CSS 变量到 :root 并设置 data-theme 属性（深色模式触发 [data-theme="dark"] 覆盖）
        applyThemeToCSS(theme);
        set({
          themeId: id,
          theme,
          colors: theme.colors,
          antdTheme: getAntdThemeConfig(theme),
        });
      },
    }),
    {
      name: 'xianyu-theme',
      // 只持久化 themeId
      partialize: (state) => ({ themeId: state.themeId }),
      // 从存储恢复时重新计算派生状态
      onRehydrateStorage: () => (state) => {
        if (state) {
          const theme = getThemeById(state.themeId);
          state.theme = theme;
          state.colors = theme.colors;
          state.antdTheme = getAntdThemeConfig(theme);
          // 应用 CSS 变量与 data-theme 属性
          applyThemeToCSS(theme);
        }
      },
    }
  )
);

/** 初始化主题（在应用启动时调用一次） */
export function initTheme(): void {
  const state = useThemeStore.getState();
  applyThemeToCSS(state.theme);
}
