// 闲鱼记账系统 - 类型定义

// 客户等级
export type CustomerLevel = 'normal' | 'vip' | 'core';

// 交易状态
export type TransactionStatus = 'pending' | 'completed' | 'aftersales' | 'closed';

// 来源类型
export type SourceType = 'direct' | 'introduced' | 'repeat';

// 销售渠道（与 source_type 正交：在哪个平台成交）
export type ChannelType = 'xianyu' | 'wechat' | 'other';

// 售后状态
export type AfterSalesStatus = 'pending' | 'processing' | 'resolved' | 'closed';

// 解决方式
export type SolutionType = 'remote' | 'reship' | 'refund' | 'other';

// 返利状态
export type RebateStatus = 'pending' | 'paid' | 'cancelled';

// 返利基数
export type RebateBase = 'profit' | 'sale';

// 通知类型
export type NotificationType =
  | 'warranty_expiring'
  | 'aftersales_pending'
  | 'rebate_pending'
  | 'customer_recall'
  | 'mail_alert'
  | 'account_paused'
  | 'account_recovered';

// 通知状态
export type NotificationStatus = 'unread' | 'read' | 'dismissed';

// 质保状态
export type WarrantyStatusType = 'active' | 'urgent' | 'expired' | 'none';

// 客户表
export interface Customer {
  id?: number;
  xianyu_nickname: string;
  contact_info?: string;
  first_trade_at?: Date;
  total_spent: number;
  trade_count: number;
  level: CustomerLevel;
  tags: string[];
  is_blacklist: boolean;
  notes?: string;
  version: number;
  created_at: Date;
  updated_at: Date;
  deleted_at?: Date;
}

// 交易记录表
export interface Transaction {
  id?: number;
  customer_id: number;
  /** 后端 list 接口内联返回的客户昵称（仅查询结果中出现，写入时不传） */
  customer_name?: string;
  xianyu_order_no?: string;
  product_name: string;
  product_template_id?: number;
  sale_price: number;
  cost_price: number;
  profit: number;
  trade_at: Date;
  shipped_at?: Date;
  status: TransactionStatus;
  warranty_end?: Date;
  warranty_days: number;
  source_type: SourceType;
  channel: ChannelType;
  source_customer_id?: number;
  notes?: string;
  attachments: string[];
  version: number;
  created_at: Date;
  updated_at: Date;
  deleted_at?: Date;
}

// 客户关联关系表
export interface CustomerLink {
  id?: number;
  referrer_id: number;
  buyer_id: number;
  transaction_id: number;
  level: number;
  created_at: Date;
}

// 售后工单表
export interface AfterSales {
  id?: number;
  transaction_id: number;
  issue_desc: string;
  status: AfterSalesStatus;
  solution_type?: SolutionType;
  solution_desc?: string;
  created_at: Date;
  resolved_at?: Date;
  duration_hours?: number;
  attachments: string[];
  // 创建工单时交易的原始状态，用于工单关闭后正确恢复（P-20 修复）
  original_transaction_status?: TransactionStatus;
  // 软删除标记（P0-4 级联策略：软删除交易时同步软删除关联工单）
  deleted_at?: Date;
}

// 返利记录表
export interface RebateRecord {
  id?: number;
  referrer_id: number;
  buyer_id: number;
  transaction_id: number;
  amount: number;
  rate: number;
  status: RebateStatus;
  paid_at?: Date;
  notes?: string;
  created_at: Date;
}

// 运营支出记录（擦亮费、推广费等）
export interface OperatingExpense {
  id: number;
  category: string;
  amount: number;
  occurred_at: Date;
  notes?: string;
  created_at: Date;
  updated_at: Date;
}

// 商品模板表
export interface ProductTemplate {
  id?: number;
  name: string;
  default_cost: number;
  default_sale_price?: number;
  category?: string;
  image_url?: string;
  warranty_days: number;
  is_active: boolean;
  source_xianyu_account_id?: number;
  source_xianyu_item_id?: string;
  created_at: Date;
  updated_at: Date;
}

// 质保延长记录表
export interface WarrantyExtension {
  id?: number;
  transaction_id: number;
  old_end: Date;
  new_end: Date;
  extended_days: number;
  reason?: string;
  created_at: Date;
}

// 通知记录表
export interface NotificationRecord {
  id?: number;
  type: NotificationType;
  ref_id?: number;
  title: string;
  content: string;
  status: NotificationStatus;
  scheduled_at: Date;
  sent_at?: Date;
  created_at: Date;
}

export interface PendingSummary {
  warrantyUrgent: number;
  afterSalesPending: number;
  rebatePending: number;
}

// 客户标签表
export interface CustomerTag {
  id?: number;
  name: string;
  color?: string;
  is_system: boolean;
  created_at: Date;
}

// 客户-标签关联表
export interface CustomerTagRelation {
  id?: number;
  customer_id: number;
  tag_id: number;
  created_at: Date;
}

// 附件表（存储图片 Blob，供交易/售后工单引用）
export interface Attachment {
  id: number;
  name: string;
  type: string;
  size: number;
  created_at: Date;
}

// 邮件发送记录表
export interface MailRecord {
  id?: number;
  to: string; // 收件人邮箱
  customer_name?: string; // 客户昵称
  email_account: string; // 邮箱账号
  gpt_password: string; // GPT 密码
  token_url: string; // 动态令牌网址
  email_password: string; // 邮箱密码
  subject: string; // 邮件主题
  status: 'success' | 'failed'; // 发送状态
  error?: string; // 失败原因
  message_id?: string; // 邮件 ID
  sent_at: Date; // 发送时间
}

// 操作审计日志模块
export type AuditModule = 'transaction' | 'customer' | 'aftersales' | 'rebate' | 'settings' | 'mail' | 'warranty' | 'system' | 'order';

// 操作审计日志表
export interface OperationLog {
  id?: number;
  module: AuditModule;
  action: string;          // 操作类型：create / update / delete / status_change / config / send 等
  target_id?: number;      // 受影响实体 ID
  target_name?: string;    // 可读标识（客户昵称、商品名等）
  detail?: string;         // 操作详情摘要
  created_at: Date;
}

// 系统设置表
export interface Settings {
  id?: number;
  warranty_days: number;
  rebate_rate: number;
  rebate_base: RebateBase;
  vip_threshold: number;
  core_threshold: number;
  vip_trade_count: number;
  core_trade_count: number;
  recall_days: number;
  backup_path?: string;
  // 邮件发送 SMTP 配置（QQ 邮箱）
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_pass: string;
  smtp_from?: string;
}

// 质保状态结果
export interface WarrantyStatus {
  type: WarrantyStatusType;
  label: string;
  color: string;
  daysLeft: number;
}

// 推荐树节点
export interface ReferralTreeNode {
  id: number;
  name: string;
  level: number;
  totalRevenue: number;
  children: ReferralTreeNode[];
}

// 财务概览
export interface FinanceOverview {
  totalIncome: number;
  totalCost: number;
  totalProfit: number;
  operatingExpense?: number;
  profitRate: number;
  tradeCount: number;
  prevIncome: number;
  prevProfit: number;
  prevTradeCount: number;
  incomeChange: number;
  profitChange: number;
  tradeCountChange: number;
}

// 趋势数据点
export interface TrendPoint {
  date: string;
  income: number;
  cost: number;
  profit: number;
}

// 月度对比数据点
export interface MonthlyComparisonPoint {
  month: string;       // 月份标签，如 "2026-06" 或 "6月"
  income: number;      // 收入
  cost: number;        // 成本
  profit: number;      // 利润
  tradeCount: number;  // 交易笔数
}

// 渠道占比数据点（财务报表按销售渠道拆分）
export interface ChannelBreakdownItem {
  channel: ChannelType;
  income: number;
  cost: number;
  profit: number;
  count: number;
}

// 商品利润统计
export interface ProductProfitStat {
  productName: string;
  totalProfit: number;
  totalIncome: number;
  totalCost: number;
  count: number;
  profitRate: number;
}

// 客户价值统计
export interface CustomerValueStat {
  customerId: number;
  nickname: string;
  totalSpent: number;
  tradeCount: number;
  level: CustomerLevel;
}

// 介绍人排行
export interface ReferrerRanking {
  referrerId: number;
  nickname: string;
  introducedCount: number;
  broughtRevenue: number;
  paidRebate: number;
  pendingRebate: number;
}

// 交易录入输入
export interface TransactionInput {
  customer_id: number;
  xianyu_order_no?: string;
  product_name: string;
  product_template_id?: number;
  sale_price: number;
  cost_price: number;
  trade_at: Date;
  shipped_at?: Date;
  status: TransactionStatus;
  warranty_days: number;
  source_type: SourceType;
  channel: ChannelType;
  source_customer_id?: number;
  notes?: string;
  attachments?: string[];
}

// 售后工单输入
export interface AfterSalesInput {
  transaction_id: number;
  issue_desc: string;
  attachments?: string[];
}

// 默认设置
export const DEFAULT_SETTINGS: Settings = {
  id: 1,
  warranty_days: 30,
  rebate_rate: 0.1,
  rebate_base: 'profit',
  vip_threshold: 500,
  core_threshold: 2000,
  vip_trade_count: 5,
  core_trade_count: 20,
  recall_days: 30,
  smtp_host: 'smtp.qq.com',
  smtp_port: 465,
  smtp_user: '',
  smtp_pass: '',
};

// ==================== 闲鱼账号与订单同步 ====================

// 闲鱼账号状态
export type XianyuAccountStatus = 'online' | 'invalid' | 'risk' | 'paused';

// 闲鱼账号
export interface XianyuAccount {
  id: number;
  nickname: string;
  unb?: string;
  status: XianyuAccountStatus;
  last_sync_at?: Date;
  last_error?: string;
  // P3 安全调度字段
  auto_sync_enabled: boolean;
  auto_sync_interval_minutes: number;
  consecutive_failures: number;
  paused_at?: Date;
  created_at: Date;
  updated_at: Date;
}

// 创建闲鱼账号输入（含明文 cookies，提交后端加密存储）
export interface XianyuAccountInput {
  nickname: string;
  cookies: string;
}

// 账号 Cookie 校验结果
export interface XianyuAccountTestResult {
  valid: boolean;
  unb?: string;
  message: string;
}

// CookieCloud 自动续 Cookie 配置状态（不包含任何密钥值）
export interface CookieCloudConfigStatus {
  enabled: boolean;
  configured_keys: string[];
  missing_keys: string[];
  domain_keyword: string;
  message: string;
  next_step: string;
}

// 订单同步结果
export interface XianyuSyncResult {
  success: boolean;
  fetched: number;
  created_count: number;
  skipped_count: number;
  error?: string;
}

export interface XianyuItemSyncResult {
  success: boolean;
  fetched: number;
  upserted_count: number;
  error?: string;
}

export interface XianyuItemImportResult {
  created_count: number;
  skipped_count: number;
}

export interface XianyuItem {
  id: number;
  account_id: number;
  item_id: string;
  title?: string;
  price: number;
  item_status?: string;
  image_url?: string;
  projected_template_id?: number;
  last_seen_at: Date;
  created_at: Date;
  updated_at: Date;
}

// 闲鱼订单镜像（不含 raw_order，避免前端暴露平台原始响应）
export interface XianyuOrder {
  id: number;
  account_id: number;
  order_no: string;
  order_status?: string;
  buyer_nick?: string;
  product_name?: string;
  sale_price: number;
  trade_at?: Date;
  projected_transaction_id?: number;
  last_seen_at: Date;
  created_at: Date;
  updated_at: Date;
}

// 同步日志
export interface XianyuSyncLog {
  id: number;
  account_id: number;
  status: 'success' | 'failed';
  fetched: number;
  created_count: number;
  skipped_count: number;
  error?: string;
  created_at: Date;
}
