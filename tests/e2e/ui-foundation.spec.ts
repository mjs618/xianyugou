import { expect, test, type Page, type Route } from '@playwright/test';

const emptyOverview = {
  totalIncome: 0,
  totalCost: 0,
  totalProfit: 0,
  operatingExpense: 0,
  profitRate: 0,
  tradeCount: 0,
  prevIncome: 0,
  prevProfit: 0,
  prevTradeCount: 0,
  incomeChange: 0,
  profitChange: 0,
  tradeCountChange: 0,
};

function responseFor(route: Route): unknown {
  const path = new URL(route.request().url()).pathname;
  if (path === '/api/auth/token-status') return { token_configured: true };
  if (path === '/api/auth/verify-token') return { valid: true };
  if (path === '/api/health') return { ok: true, service: 'xianyu-backend' };
  if (path === '/api/xianyu/accounts') {
    return ['0618', '6674', '主号'].map((nickname, index) => ({
      id: index + 1,
      nickname,
      unb: `mock-${index + 1}`,
      status: 'paused',
      last_sync_at: '2026-07-15T12:09:00Z',
      last_error: 'Cookie 已过期，需更新后恢复',
      auto_sync_enabled: index === 0,
      auto_sync_interval_minutes: 60,
      consecutive_failures: 3,
      paused_at: '2026-07-15T13:00:00Z',
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-15T13:00:00Z',
    }));
  }
  if (path === '/api/xianyu/cookiecloud/status') {
    return {
      enabled: false,
      configured_keys: [],
      missing_keys: ['COOKIE_CLOUD_HOST', 'COOKIE_CLOUD_UUID', 'COOKIE_CLOUD_PASSWORD'],
      domain_keyword: 'goofish.com',
      message: 'CookieCloud 未配置完整，Cookie 过期后不会自动续期。',
      next_step: '请在部署环境中完成配置。',
    };
  }
  if (path === '/api/settings') {
    return {
      id: 1,
      warranty_days: 30,
      rebate_rate: 0.1,
      rebate_base: 'profit',
      vip_threshold: 500,
      core_threshold: 2000,
      vip_trade_count: 5,
      core_trade_count: 20,
      recall_days: 30,
      smtp_host: '',
      smtp_port: 465,
      smtp_user: '',
      smtp_pass: '',
    };
  }
  if (path === '/api/notifications/unread-count') return { count: 0 };
  if (path === '/api/notifications/pending-summary') {
    return { warrantyUrgent: 0, afterSalesPending: 0, rebatePending: 0 };
  }
  if (path === '/api/notifications/reminders/check') return { created: [] };
  if (path === '/api/reply-assistant/settings') {
    return {
      id: 1,
      enabled: true,
      ai_enabled: false,
      api_base_url: '',
      api_key_configured: false,
      model: '',
      system_prompt: '',
    };
  }
  if (path === '/api/reply-assistant/rules') return [];
  if (path === '/api/reply-assistant/suggestions') {
    return {
      reply: '请通过闲鱼订单申请售后。',
      source: 'rule',
      matched_rule_id: 1,
      risk_level: 'manual_required',
      risk_reasons: ['退款售后'],
      copy_allowed: true,
    };
  }
  if (path === '/api/xianyu/accounts') {
    return [{
      id: 1,
      nickname: '主账号',
      status: 'online',
      auto_sync_enabled: false,
      auto_sync_interval_minutes: 120,
      consecutive_failures: 0,
      created_at: '2026-07-15T00:00:00Z',
      updated_at: '2026-07-15T00:00:00Z',
    }];
  }
  if (path === '/api/product-templates') return [];
  if (path === '/api/metrics') {
    return {
      timestamp: '2026-07-15T15:00:00Z',
      accounts: { total: 1, online: 1, paused: 0, invalid: 0 },
      sync: {
        last_24h_success: 2,
        last_24h_failed: 0,
        last_24h_fetched_orders: 3,
        last_24h_created_transactions: 1,
        last_error: null,
        last_sync_at: '2026-07-15T14:30:00Z',
      },
      backup: {
        last_backup_at: '2026-07-15T02:00:00Z',
        backup_count: 7,
        backup_dir_exists: true,
      },
      notifications_unread: 0,
      scheduler_running: true,
    };
  }
  if (path === '/api/finance/overview') return emptyOverview;
  if (path === '/api/finance/new-customer-count') return { count: 0 };
  if (
    path === '/api/finance/trend' ||
    path === '/api/finance/products' ||
    path === '/api/finance/channel-breakdown' ||
    path === '/api/referral/rankings' ||
    path === '/api/warranty/urgent' ||
    path === '/api/transactions' ||
    path === '/api/customers'
  ) {
    return [];
  }
  return [];
}

async function mockApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(responseFor(route)),
    });
  });
}

async function unlock(page: Page) {
  await page.goto('/');
  await expect(page.getByText('解锁系统')).toBeVisible();
  await page.getByLabel('API Token').fill('browser-test-token');
  await page.getByRole('button', { name: '验证并进入' }).click();
  await expect(page.getByRole('heading', { level: 1, name: '首页' })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('解锁后进入具备基础语义的首页', async ({ page }) => {
  await unlock(page);

  await expect(page.locator('a.skip-link')).toHaveAttribute('href', '#main-content');
  await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible();
  await expect(page.locator('#main-content')).toBeVisible();
  await expect(page.getByRole('link', { name: '本月总收入，查看详情' })).toBeVisible();
});

test('390px 移动视口可打开完整导航', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await unlock(page);

  await page.getByRole('button', { name: '打开全部导航' }).click();
  const fullNavigation = page.getByRole('navigation', { name: '全部导航' });
  await expect(fullNavigation).toBeVisible();
  await expect(fullNavigation.getByText('回复助手')).toBeVisible();
  await expect(fullNavigation.getByText('订单同步')).toBeVisible();
  await expect(fullNavigation.getByText('设置')).toBeVisible();
  await expect(page.getByRole('navigation', { name: '移动快捷导航' })).toBeVisible();
});

test('回复助手生成规则候选并提示人工核对', async ({ page }) => {
  await unlock(page);
  await page.goto('/reply-assistant');

  await expect(page.getByRole('heading', { level: 2, name: '闲鱼回复助手' })).toBeVisible();
  await page.getByPlaceholder('粘贴买家的最新消息').fill('我想退款');
  await page.getByRole('button', { name: '生成候选回复' }).click();

  await expect(page.getByText('固定规则', { exact: true })).toBeVisible();
  await expect(page.getByText('人工核对')).toBeVisible();
  await expect(page.getByText('触发原因：退款售后')).toBeVisible();
});

test('设置页可查看真实指标结构的运行状态', async ({ page }) => {
  await unlock(page);
  await page.goto('/settings');
  await expect(page.getByRole('heading', { level: 1, name: '设置' })).toBeVisible();
  await page.getByRole('tab', { name: /运行状态/ }).click();

  await expect(page.getByText('在线账号')).toBeVisible();
  await expect(page.getByText('运行详情')).toBeVisible();
  await expect(page.getByText('运行中')).toBeVisible();
  await expect(page.getByText('7份')).toBeVisible();
});

test('订单同步页优先展示待处理任务和账号主操作', async ({ page }) => {
  await unlock(page);
  await page.goto('/order-sync');

  await expect(page.getByRole('region', { name: '同步状态总览' })).toBeVisible();
  await expect(page.getByText('3 个账号需要处理')).toBeVisible();
  await expect(page.getByText('0618、6674、主号')).toBeVisible();
  await expect(page.getByRole('button', { name: '更新 Cookie 0618' })).toBeVisible();
  await expect(page.getByRole('button', { name: '校验并恢复 0618' })).toBeVisible();

  const help = page.getByRole('button', { name: /同步说明与 Cookie 获取方法/ });
  await expect(help).toHaveAttribute('aria-expanded', 'false');
});

test('390px 订单同步页保持单列且没有页面级横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await unlock(page);
  await page.goto('/order-sync');

  await expect(page.getByRole('region', { name: '同步状态总览' })).toBeVisible();
  await expect(page.getByRole('button', { name: '更新 Cookie 0618' })).toBeVisible();
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
