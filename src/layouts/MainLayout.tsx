import { useEffect, useState, type ReactNode } from 'react';
import { Layout, Menu, Button, Drawer, Space, Tooltip, Grid, Badge } from 'antd';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
  HomeOutlined,
  FileTextOutlined,
  TeamOutlined,
  ShareAltOutlined,
  SafetyCertificateOutlined,
  ToolOutlined,
  BarChartOutlined,
  SettingOutlined,
  PlusOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ArrowUpOutlined,
  MailOutlined,
  SearchOutlined,
  CloudSyncOutlined,
  MenuOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { useAppStore } from '@/store/useAppStore';
import { runAllReminderChecks } from '@/services/notificationService';
import GlobalSearch, { invalidateSearchCache } from '@/components/GlobalSearch';
import NotificationCenter from '@/components/NotificationCenter';
import { getNavigationBadgeCount } from '@/utils/navigationBadges';
import { buildLayoutMenuItems, LAYOUT_NAVIGATION_ROUTES } from '@/utils/layoutNavigation';
import { REMINDER_CHECK_INTERVAL_MS, SCROLL_TOP_THRESHOLD } from '@/config/constants';

const { Sider, Header, Content } = Layout;
const { useBreakpoint } = Grid;

const navigationIcons = {
  '/': <HomeOutlined />,
  '/transactions': <FileTextOutlined />,
  '/customers': <TeamOutlined />,
  '/referral': <ShareAltOutlined />,
  '/warranty': <SafetyCertificateOutlined />,
  '/after-sales': <ToolOutlined />,
  '/finance': <BarChartOutlined />,
  '/send-mail': <MailOutlined />,
  '/reply-assistant': <MessageOutlined />,
  '/order-sync': <CloudSyncOutlined />,
  '/settings': <SettingOutlined />,
} satisfies Record<(typeof LAYOUT_NAVIGATION_ROUTES)[number]['key'], ReactNode>;

const menuItems = LAYOUT_NAVIGATION_ROUTES.map((item) => ({
  ...item,
  icon: navigationIcons[item.key],
}));

// 移动端底部导航项（精简为 5 个主要功能）
const mobileNavItems = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/transactions', icon: <FileTextOutlined />, label: '交易' },
  { key: '/customers', icon: <TeamOutlined />, label: '客户' },
  { key: '/warranty', icon: <SafetyCertificateOutlined />, label: '质保' },
  { key: '/finance', icon: <BarChartOutlined />, label: '财务' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md = 768px 以下为移动端
  const { collapsed, setCollapsed, refreshAll, pendingSummary } = useAppStore();
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);

  // 移动端自动折叠侧边栏
  useEffect(() => {
    if (isMobile) {
      setCollapsed(true);
    }
  }, [isMobile, setCollapsed]);

  useEffect(() => {
    refreshAll();
    runAllReminderChecks().then(() => refreshAll()).catch(() => {});
    const timer = setInterval(() => {
      runAllReminderChecks().then(() => refreshAll()).catch(() => {});
    }, REMINDER_CHECK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refreshAll]);

  useEffect(() => {
    refreshAll();
    // 页面切换时清除搜索缓存，保证下次搜索加载最新数据
    invalidateSearchCache();
    // 页面切换时关闭移动端搜索抽屉
    setSearchOpen(false);
    setNavigationOpen(false);
  }, [location.pathname, refreshAll]);

  // 滚动监听 - 控制回到顶部按钮
  const handleScroll = () => {
    setShowScrollTop(window.scrollY > SCROLL_TOP_THRESHOLD);
  };
  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const selectedKey = (() => {
    if (location.pathname === '/') return '/';
    const match = menuItems.find((m) => m.key !== '/' && location.pathname.startsWith(m.key));
    return match ? match.key : '/';
  })();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      {!isMobile && (
        <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          width={208}
          style={{ background: 'var(--color-surface)', borderRight: '1px solid var(--color-border)', position: 'sticky', top: 0, height: '100vh' }}
        >
          <div
            style={{
              height: 56,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              borderBottom: '1px solid var(--color-border)',
            }}
          >
            <div style={{ width: 30, height: 30, borderRadius: 6, background: 'var(--theme-primary)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 16 }}>
              闲
            </div>
            {!collapsed && <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-dark)', letterSpacing: 0.3 }}>闲鱼记账助手</span>}
          </div>
          <nav aria-label="主导航">
            <Menu
              mode="inline"
              selectedKeys={[selectedKey]}
              items={buildLayoutMenuItems(menuItems, collapsed, pendingSummary)}
              onClick={({ key }) => navigate(key)}
              style={{ borderRight: 'none', marginTop: 8, fontSize: 14 }}
            />
          </nav>
        </Sider>
      )}
      <Layout>
        <Header
          style={{
            background: 'var(--color-surface)',
            padding: isMobile ? '0 12px' : '0 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--color-border)',
            position: 'sticky',
            top: 0,
            zIndex: 10,
            gap: 8,
            height: 56,
          }}
        >
          <Space size={8}>
            {isMobile && (
              <Button
                type="text"
                shape="circle"
                size="small"
                icon={<MenuOutlined />}
                aria-label="打开全部导航"
                onClick={() => setNavigationOpen(true)}
              />
            )}
            {!isMobile && (
              <Button type="text" aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'} onClick={() => setCollapsed(!collapsed)} icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} />
            )}
            <h1 style={{ color: 'var(--color-text-secondary)', fontSize: 13, fontWeight: 500, margin: 0 }} className="text-ellipsis">
              {menuItems.find((m) => m.key === selectedKey)?.label || '首页'}
            </h1>
          </Space>
          <Space size={isMobile ? 4 : 12}>
            {!isMobile && <GlobalSearch />}
            {isMobile && (
              <Button type="text" shape="circle" size="small" icon={<SearchOutlined />} aria-label="搜索" onClick={() => setSearchOpen(true)} />
            )}
            <Tooltip title="记一笔">
              <Button type="primary" icon={<PlusOutlined />} aria-label="记一笔" onClick={() => navigate('/transactions/new')} size={isMobile ? 'small' : 'middle'}>
                {isMobile ? '' : '记一笔'}
              </Button>
            </Tooltip>
            <NotificationCenter isMobile={isMobile} />
            {!isMobile && (
              <Tooltip title="设置">
                <Button type="text" icon={<SettingOutlined />} aria-label="设置" onClick={() => navigate('/settings')} />
              </Tooltip>
            )}
          </Space>
        </Header>
        <Content
          id="main-content"
          tabIndex={-1}
          className={isMobile ? 'mobile-content' : undefined}
          style={{ padding: isMobile ? 12 : 20, overflow: 'auto', paddingBottom: isMobile ? 68 : 20 }}
        >
          <div key={location.pathname} className="page-fade-enter">
            <Outlet />
          </div>
        </Content>
      </Layout>

      {/* 移动端底部导航 */}
      {isMobile && (
        <nav className="mobile-bottom-nav" aria-label="移动快捷导航">
          {mobileNavItems.map((item) => {
            const isActive = selectedKey === item.key;
            return (
              <button
                key={item.key}
                type="button"
                className={`mobile-bottom-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => navigate(item.key)}
                aria-label={item.label}
                aria-current={isActive ? 'page' : undefined}
              >
                {item.icon}
                <Badge count={getNavigationBadgeCount(item.key, pendingSummary)} size="small" offset={[8, -2]}>
                  <span style={{ marginTop: 2 }}>{item.label}</span>
                </Badge>
              </button>
            );
          })}
        </nav>
      )}

      {/* 回到顶部按钮 */}
      {showScrollTop && (
        <button type="button" className="scroll-to-top visible" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="回到顶部">
          <ArrowUpOutlined />
        </button>
      )}

      {/* 移动端搜索抽屉 */}
      <Drawer
        title="全部导航"
        placement="left"
        open={navigationOpen}
        onClose={() => setNavigationOpen(false)}
        width={280}
        className="mobile-navigation-drawer"
        bodyStyle={{ padding: '8px 0', overscrollBehavior: 'contain' }}
      >
        <nav aria-label="全部导航">
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={buildLayoutMenuItems(menuItems, false, pendingSummary)}
            onClick={({ key }) => {
              setNavigationOpen(false);
              navigate(key);
            }}
            style={{ borderInlineEnd: 'none' }}
          />
        </nav>
      </Drawer>

      <Drawer
        title="搜索"
        placement="top"
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        bodyStyle={{ padding: 16 }}
        height={140}
      >
        <GlobalSearch />
      </Drawer>
    </Layout>
  );
}
