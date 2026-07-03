import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { Spin } from 'antd';
import MainLayout from './layouts/MainLayout';
import ErrorBoundary from './components/ErrorBoundary';

// 路由懒加载 - 按需加载页面组件，减少初始包体积
const Dashboard = lazy(() => import('./pages/Dashboard'));
const TransactionList = lazy(() => import('./pages/transactions/TransactionList'));
const TransactionForm = lazy(() => import('./pages/transactions/TransactionForm'));
const TransactionDetail = lazy(() => import('./pages/transactions/TransactionDetail'));
const CustomerList = lazy(() => import('./pages/customers/CustomerList'));
const CustomerDetail = lazy(() => import('./pages/customers/CustomerDetail'));
const ReferralGraph = lazy(() => import('./pages/ReferralGraph'));
const WarrantyBoard = lazy(() => import('./pages/WarrantyBoard'));
const AfterSalesList = lazy(() => import('./pages/AfterSalesList'));
const FinanceReport = lazy(() => import('./pages/FinanceReport'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const SendMail = lazy(() => import('./pages/SendMail'));
const OrderSync = lazy(() => import('./pages/OrderSync'));

const PageLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

const withSuspense = (element: React.ReactNode) => (
  <ErrorBoundary>
    <Suspense fallback={<PageLoading />}>{element}</Suspense>
  </ErrorBoundary>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: withSuspense(<Dashboard />) },
      { path: 'transactions', element: withSuspense(<TransactionList />) },
      { path: 'transactions/new', element: withSuspense(<TransactionForm />) },
      { path: 'transactions/:id/edit', element: withSuspense(<TransactionForm />) },
      { path: 'transactions/:id', element: withSuspense(<TransactionDetail />) },
      { path: 'customers', element: withSuspense(<CustomerList />) },
      { path: 'customers/:id', element: withSuspense(<CustomerDetail />) },
      { path: 'referral', element: withSuspense(<ReferralGraph />) },
      { path: 'warranty', element: withSuspense(<WarrantyBoard />) },
      { path: 'after-sales', element: withSuspense(<AfterSalesList />) },
      { path: 'finance', element: withSuspense(<FinanceReport />) },
      { path: 'send-mail', element: withSuspense(<SendMail />) },
      { path: 'order-sync', element: withSuspense(<OrderSync />) },
      { path: 'settings', element: withSuspense(<SettingsPage />) },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
