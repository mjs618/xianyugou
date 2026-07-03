import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  root: process.cwd(),
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
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
  },
} as any);
