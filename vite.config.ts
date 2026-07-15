import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => ({
  plugins: [react({ fastRefresh: mode !== 'test' })],
  root: __dirname,
  base: '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
  },
  optimizeDeps: {
    include: [
      'antd',
      'antd/locale/zh_CN',
      'react',
      'react-dom',
      'react-dom/client',
      'react-router-dom',
      'dayjs',
      'dayjs/locale/zh-cn',
      'zustand',
      'recharts',
      'reactflow',
      '@ant-design/icons',
    ],
  },
  build: {
    // 仅将体积大、跨路由共用的第三方库拆为独立 vendor chunk，
    // 保留 rollup 对 antd 等库的按路由 tree-shaking，避免合并后单 chunk 过大。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          // xlsx 已在业务代码中动态 import，显式命名保持独立 chunk
          if (id.includes('xlsx')) return 'xlsx-vendor';
          // recharts 被 Dashboard / FinanceReport 共用，单独成块避免重复打包
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) {
            return 'recharts-vendor';
          }
          // reactflow 被 ReferralGraph / CustomerDetail 共用
          if (id.includes('reactflow')) return 'reactflow-vendor';
          // react 核心：变动极少，独立成块最大化缓存命中
          if (
            id.includes('react-router') ||
            id.includes('react-dom') ||
            id.includes('/react/') ||
            id.includes('scheduler')
          ) {
            return 'react-vendor';
          }
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/e2e/**'],
  },
} as any));
