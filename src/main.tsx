import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import ErrorBoundary from './components/ErrorBoundary';
import { useThemeStore, initTheme } from './store/useThemeStore';
import { migrateEncryptMailRecords } from './services/mailRecordService';
import { runAllCleanup } from './services/trashService';
import 'dayjs/locale/zh-cn';
import dayjs from 'dayjs';
import './styles/global.css';

dayjs.locale('zh-cn');

// 初始化 CSS 变量（在 React 渲染前执行，避免首屏闪烁）
initTheme();

// 邮件记录与清理任务已迁移至后端，前端启动不再做本地迁移/清理
// （migrateEncryptMailRecords / runAllCleanup 均为 no-op，保留调用兼容）
migrateEncryptMailRecords().catch(() => {});
runAllCleanup().catch(() => {});

function Root() {
  const antdTheme = useThemeStore((s) => s.antdTheme);
  return (
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>
        <RouterProvider router={router} />
      </AntdApp>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </React.StrictMode>
);
