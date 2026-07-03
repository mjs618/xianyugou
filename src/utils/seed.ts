import { getSettings } from '@/services/settingsService';
import { createCustomer } from '@/services/customerService';
import { createTransaction } from '@/services/transactionService';
import { createTemplate } from '@/services/productTemplateService';
import { listTransactions } from '@/services/transactionService';
import dayjs from 'dayjs';

// 检查是否已有数据（查后端，因数据层已迁移）
export async function hasData(): Promise<boolean> {
  try {
    const list = await listTransactions();
    return list.length > 0;
  } catch {
    return false;
  }
}

// 灌入演示数据
export async function seedDemoData(): Promise<void> {
  if (await hasData()) return;

  // 商品模板
  const tpl1 = await createTemplate({ name: '软件激活码（年卡）', default_cost: 30, default_sale_price: 128, category: '激活码', warranty_days: 30 });
  const tpl2 = await createTemplate({ name: '会员代充（季度）', default_cost: 20, default_sale_price: 48, category: '代充', warranty_days: 30 });
  const tpl3 = await createTemplate({ name: '技术支持服务', default_cost: 0, default_sale_price: 50, category: '服务', warranty_days: 30 });
  const tpl4 = await createTemplate({ name: '软件激活码（月卡）', default_cost: 5, default_sale_price: 18, category: '激活码', warranty_days: 30 });

  // 客户
  const cA = await createCustomer({ xianyu_nickname: '数码达人小王', contact_info: 'wx_wang001' });
  const cB = await createCustomer({ xianyu_nickname: '游戏玩家老李', contact_info: 'wx_li002' });
  const cC = await createCustomer({ xianyu_nickname: '设计师阿May', contact_info: 'wx_may003' });
  const cD = await createCustomer({ xianyu_nickname: '学生党小张', contact_info: 'wx_zhang004' });
  const cE = await createCustomer({ xianyu_nickname: '上班族大刘', contact_info: 'wx_liu005' });
  const cF = await createCustomer({ xianyu_nickname: '极客小哥', contact_info: 'wx_geek006', is_blacklist: false });

  const settings = await getSettings();
  const now = new Date();

  // 交易：A 是根，介绍 B、C；B 介绍 D
  await createTransaction({
    customer_id: cA.id!,
    product_name: '软件激活码（年卡）',
    product_template_id: tpl1.id,
    sale_price: 128,
    cost_price: 30,
    trade_at: dayjs(now).subtract(20, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'direct',
  });

  await createTransaction({
    customer_id: cB.id!,
    product_name: '会员代充（季度）',
    product_template_id: tpl2.id,
    sale_price: 48,
    cost_price: 20,
    trade_at: dayjs(now).subtract(15, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'introduced',
    source_customer_id: cA.id!,
  });

  await createTransaction({
    customer_id: cC.id!,
    product_name: '技术支持服务',
    product_template_id: tpl3.id,
    sale_price: 50,
    cost_price: 0,
    trade_at: dayjs(now).subtract(10, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'introduced',
    source_customer_id: cA.id!,
  });

  await createTransaction({
    customer_id: cD.id!,
    product_name: '软件激活码（月卡）',
    product_template_id: tpl4.id,
    sale_price: 18,
    cost_price: 5,
    trade_at: dayjs(now).subtract(5, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'introduced',
    source_customer_id: cB.id!,
  });

  // 即将到期交易（2天后到期）
  await createTransaction({
    customer_id: cE.id!,
    product_name: '软件激活码（年卡）',
    product_template_id: tpl1.id,
    sale_price: 128,
    cost_price: 30,
    trade_at: dayjs(now).subtract(29, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'direct',
  });

  // 待处理交易
  await createTransaction({
    customer_id: cF.id!,
    product_name: '会员代充（季度）',
    product_template_id: tpl2.id,
    sale_price: 48,
    cost_price: 20,
    trade_at: dayjs(now).subtract(1, 'day').toDate(),
    status: 'pending',
    warranty_days: 30,
    source_type: 'direct',
  });

  // 本月交易补充
  await createTransaction({
    customer_id: cA.id!,
    product_name: '技术支持服务',
    product_template_id: tpl3.id,
    sale_price: 50,
    cost_price: 0,
    trade_at: dayjs(now).subtract(3, 'day').toDate(),
    status: 'completed',
    warranty_days: 30,
    source_type: 'repeat',
  });
}
