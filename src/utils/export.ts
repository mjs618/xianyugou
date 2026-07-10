import type { Transaction, Customer, FinanceOverview, ProductProfitStat, CustomerValueStat, RebateRecord } from '@/types';
import type { WorkSheet } from 'xlsx';
import { formatDate } from './date';
import { isEncrypted, encryptWithPassword, decryptWithPassword, isEncryptedBackup } from './crypto';
import { apiClient } from '@/services/apiClient';

// 导出 JSON 备份（数据层已迁移后端，从后端 /api/migrate/export 获取全量明文备份）
// P0-2：支持可选密码加密，传入密码时整个 JSON 被加密为 backup:v1: 格式
export async function exportJSON(password?: string): Promise<string> {
  // 从后端获取明文备份（后端已解密敏感字段、附件转 Base64）
  const backup = await apiClient.get<Record<string, unknown>>('/api/migrate/export');
  const jsonStr = JSON.stringify(backup, null, 2);
  // 传入密码时整体加密备份（客户端密码派生加密，与后端无关）
  if (password) {
    return encryptWithPassword(jsonStr, password);
  }
  return jsonStr;
}

// 导入 JSON 备份（清空后恢复，含附件）
// P0-2：支持可选密码解密，自动识别加密备份格式
export async function importJSON(jsonStr: string, password?: string): Promise<void> {
  // P0-2：识别加密备份并解密
  let plainJson = jsonStr;
  if (isEncryptedBackup(jsonStr.trim())) {
    if (!password) {
      throw new Error('该备份文件已加密，请输入密码后再恢复');
    }
    try {
      plainJson = await decryptWithPassword(jsonStr.trim(), password);
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : '解密失败');
    }
  } else if (password) {
    // 文件未加密但用户提供了密码，提示文件未加密
    console.warn('备份文件未加密，传入的密码将被忽略');
  }

  const backup = JSON.parse(plainJson);
  if (!backup.data) throw new Error('无效的备份文件格式');

  // 数据层已迁移后端：调后端 /api/migrate/import 覆盖式写入
  // 后端负责清表 + 批量写入 + 敏感字段加密
  await apiClient.post('/api/migrate/import', backup);
}

// CSV 单元格转义：转义双引号 + 防御公式注入
// 1. 双引号转义为两个双引号（RFC 4180 标准）
// 2. 以 =、+、-、@、Tab、回车 开头的单元格前缀单引号，防止 Excel 公式注入
function escapeCSVCell(value: unknown): string {
  let str = String(value ?? '');
  // 防御公式注入：以危险字符开头的单元格前缀单引号
  if (/^[=+\-@\t\r]/.test(str)) {
    str = "'" + str;
  }
  // 转义内部双引号
  str = str.replace(/"/g, '""');
  // 用双引号包裹整个单元格
  return `"${str}"`;
}

// 导出 CSV（交易明细）
export function exportTransactionsCSV(transactions: Transaction[]): string {
  const header = ['交易ID', '闲鱼订单号', '商品名称', '售价', '成本', '利润', '客户ID', '交易时间', '发货时间', '状态', '质保到期', '来源类型', '备注'];
  const rows = transactions.map((t) => [
    t.id,
    t.xianyu_order_no || '',
    t.product_name,
    t.sale_price,
    t.cost_price,
    t.profit,
    t.customer_id,
    formatDate(t.trade_at, 'YYYY-MM-DD HH:mm'),
    t.shipped_at ? formatDate(t.shipped_at, 'YYYY-MM-DD HH:mm') : '',
    t.status,
    t.warranty_end ? formatDate(t.warranty_end, 'YYYY-MM-DD') : '',
    t.source_type,
    (t.notes || '').replace(/[\r\n,]/g, ' '),
  ]);
  const all = [header, ...rows];
  // BOM 头确保 Excel 正确识别 UTF-8
  return '\uFEFF' + all.map((r) => r.map(escapeCSVCell).join(',')).join('\n');
}

// 导出 CSV（客户明细）
export function exportCustomersCSV(customers: Customer[]): string {
  const header = ['客户ID', '闲鱼昵称', '联系方式', '等级', '累计消费', '交易笔数', '首次交易', '标签', '黑名单', '备注'];
  const rows = customers.map((c) => [
    c.id,
    c.xianyu_nickname,
    c.contact_info || '',
    c.level,
    c.total_spent,
    c.trade_count,
    c.first_trade_at ? formatDate(c.first_trade_at, 'YYYY-MM-DD') : '',
    c.tags.join('|'),
    c.is_blacklist ? '是' : '否',
    (c.notes || '').replace(/[\r\n,]/g, ' '),
  ]);
  const all = [header, ...rows];
  return '\uFEFF' + all.map((r) => r.map(escapeCSVCell).join(',')).join('\n');
}

// 触发浏览器下载
export function downloadFile(content: string, filename: string, mime = 'text/plain'): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  downloadBlob(blob, filename);
}

// 触发浏览器下载（二进制内容，用于 xlsx 等）
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ==================== Excel 导出 ====================

// 业务枚举转中文标签，提升 Excel 可读性
function transactionStatusLabel(status: string): string {
  const map: Record<string, string> = { pending: '待发货', completed: '已完成', aftersales: '售后中', closed: '已关闭' };
  return map[status] || status;
}
function sourceTypeLabel(type: string): string {
  const map: Record<string, string> = { direct: '直接下单', introduced: '客户介绍', repeat: '老客复购' };
  return map[type] || type;
}
function rebateStatusLabel(status: string): string {
  const map: Record<string, string> = { pending: '待结算', paid: '已支付', cancelled: '已取消' };
  return map[status] || status;
}
function customerLevelLabel(level: string): string {
  const map: Record<string, string> = { normal: '普通', vip: 'VIP', core: '核心' };
  return map[level] || level;
}

// 设置列宽（单位：字符宽度）
function setColWidths(ws: WorkSheet, widths: number[]): void {
  ws['!cols'] = widths.map((w) => ({ wch: w }));
}

// P1 Excel 公式注入防御：以危险字符（= + - @ Tab 回车）开头的字符串前缀单引号
// 防止 Excel/WPS 将用户输入（如商品名称、备注）解析为公式执行
function escapeExcelCell(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  if (/^[=+\-@\t\r]/.test(value)) {
    return "'" + value;
  }
  return value;
}

// 对二维数组应用公式注入防御（原地修改）
function escapeExcelAoa(rows: unknown[][]): unknown[][] {
  for (const row of rows) {
    for (let i = 0; i < row.length; i++) {
      row[i] = escapeExcelCell(row[i]);
    }
  }
  return rows;
}

// 交易明细单 Sheet Excel 导出（与 CSV 字段对齐，便于直接复用）
export async function exportTransactionsExcel(transactions: Transaction[]): Promise<Blob> {
  const XLSX = await import('xlsx');
  const header = ['交易ID', '闲鱼订单号', '商品名称', '售价', '成本', '利润', '客户ID', '交易时间', '发货时间', '状态', '质保到期', '来源类型', '备注'];
  const rows = transactions.map((t) => [
    t.id ?? '',
    t.xianyu_order_no || '',
    t.product_name,
    t.sale_price,
    t.cost_price,
    t.profit,
    t.customer_id,
    formatDate(t.trade_at, 'YYYY-MM-DD HH:mm'),
    t.shipped_at ? formatDate(t.shipped_at, 'YYYY-MM-DD HH:mm') : '',
    transactionStatusLabel(t.status),
    t.warranty_end ? formatDate(t.warranty_end, 'YYYY-MM-DD') : '',
    sourceTypeLabel(t.source_type),
    t.notes || '',
  ]);
  // P1 Excel 公式注入防御
  escapeExcelAoa(rows);
  const ws = XLSX.utils.aoa_to_sheet([header, ...rows]);
  setColWidths(ws, [8, 22, 24, 10, 10, 10, 10, 18, 18, 10, 14, 12, 30]);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '交易明细');
  const buf = XLSX.write(wb, { type: 'array', bookType: 'xlsx' });
  return new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

// 财务报表多 Sheet 导出数据载体
export interface FinanceReportExcelData {
  overview: FinanceOverview;
  rangeStart: Date;
  rangeEnd: Date;
  transactions: Transaction[];
  products: ProductProfitStat[];
  customers: CustomerValueStat[];
  rebates: RebateRecord[];
}

// 财务报表多 Sheet Excel 导出（收支总览 + 交易明细 + 商品排行 + 客户排行 + 返利记录）
export async function exportFinanceReportExcel(data: FinanceReportExcelData): Promise<Blob> {
  const XLSX = await import('xlsx');
  const wb = XLSX.utils.book_new();
  const now = formatDate(new Date(), 'YYYY-MM-DD HH:mm');

  // Sheet 1: 收支总览
  const overviewRows: (string | number)[][] = [
    ['闲鱼记账系统 - 财务报表'],
    [],
    ['报表周期', `${formatDate(data.rangeStart, 'YYYY-MM-DD')} 至 ${formatDate(data.rangeEnd, 'YYYY-MM-DD')}`],
    ['生成时间', now],
    [],
    ['指标', '数值'],
    ['总收入', data.overview.totalIncome],
    ['总成本', data.overview.totalCost],
    ['净利润', data.overview.totalProfit],
    ['利润率', `${(data.overview.profitRate * 100).toFixed(2)}%`],
    ['交易笔数', data.overview.tradeCount],
    [],
    ['上期收入', data.overview.prevIncome],
    ['上期利润', data.overview.prevProfit],
    ['上期交易数', data.overview.prevTradeCount],
    ['收入环比', `${(data.overview.incomeChange * 100).toFixed(2)}%`],
    ['利润环比', `${(data.overview.profitChange * 100).toFixed(2)}%`],
    ['交易数环比', `${(data.overview.tradeCountChange * 100).toFixed(2)}%`],
  ];
  const wsOverview = XLSX.utils.aoa_to_sheet(overviewRows);
  setColWidths(wsOverview, [16, 28]);
  XLSX.utils.book_append_sheet(wb, wsOverview, '收支总览');

  // Sheet 2: 交易明细（按当前周期过滤）
  const txHeader = ['交易ID', '闲鱼订单号', '商品名称', '售价', '成本', '利润', '客户ID', '交易时间', '发货时间', '状态', '质保到期', '来源类型', '备注'];
  const txRows = data.transactions.map((t) => [
    t.id ?? '',
    t.xianyu_order_no || '',
    t.product_name,
    t.sale_price,
    t.cost_price,
    t.profit,
    t.customer_id,
    formatDate(t.trade_at, 'YYYY-MM-DD HH:mm'),
    t.shipped_at ? formatDate(t.shipped_at, 'YYYY-MM-DD HH:mm') : '',
    transactionStatusLabel(t.status),
    t.warranty_end ? formatDate(t.warranty_end, 'YYYY-MM-DD') : '',
    sourceTypeLabel(t.source_type),
    t.notes || '',
  ]);
  // P1 Excel 公式注入防御
  escapeExcelAoa(txRows);
  const wsTx = XLSX.utils.aoa_to_sheet([txHeader, ...txRows]);
  setColWidths(wsTx, [8, 22, 24, 10, 10, 10, 10, 18, 18, 10, 14, 12, 30]);
  XLSX.utils.book_append_sheet(wb, wsTx, '交易明细');

  // Sheet 3: 商品利润排行
  const prodHeader = ['排名', '商品名称', '笔数', '收入', '利润', '利润率'];
  const prodRows = data.products.map((p, idx) => [
    idx + 1,
    p.productName,
    p.count,
    p.totalIncome,
    p.totalProfit,
    `${(p.profitRate * 100).toFixed(2)}%`,
  ]);
  // P1 Excel 公式注入防御
  escapeExcelAoa(prodRows);
  const wsProd = XLSX.utils.aoa_to_sheet([prodHeader, ...prodRows]);
  setColWidths(wsProd, [6, 28, 8, 12, 12, 10]);
  XLSX.utils.book_append_sheet(wb, wsProd, '商品利润排行');

  // Sheet 4: 客户消费排行
  const custHeader = ['排名', '客户ID', '昵称', '累计消费', '交易笔数', '等级'];
  const custRows = data.customers.map((c, idx) => [
    idx + 1,
    c.customerId,
    c.nickname,
    c.totalSpent,
    c.tradeCount,
    customerLevelLabel(c.level),
  ]);
  // P1 Excel 公式注入防御
  escapeExcelAoa(custRows);
  const wsCust = XLSX.utils.aoa_to_sheet([custHeader, ...custRows]);
  setColWidths(wsCust, [6, 10, 20, 12, 10, 8]);
  XLSX.utils.book_append_sheet(wb, wsCust, '客户消费排行');

  // Sheet 5: 返利记录
  const rbHeader = ['返利ID', '介绍人ID', '买家ID', '返利金额', '比例', '状态', '创建时间', '支付时间', '备注'];
  const rbRows = data.rebates.map((r) => [
    r.id ?? '',
    r.referrer_id,
    r.buyer_id,
    r.amount,
    `${(r.rate * 100).toFixed(2)}%`,
    rebateStatusLabel(r.status),
    formatDate(r.created_at, 'YYYY-MM-DD HH:mm'),
    r.paid_at ? formatDate(r.paid_at, 'YYYY-MM-DD HH:mm') : '',
    r.notes || '',
  ]);
  // P1 Excel 公式注入防御
  escapeExcelAoa(rbRows);
  const wsRb = XLSX.utils.aoa_to_sheet([rbHeader, ...rbRows]);
  setColWidths(wsRb, [8, 10, 10, 12, 8, 10, 18, 18, 24]);
  XLSX.utils.book_append_sheet(wb, wsRb, '返利记录');

  const buf = XLSX.write(wb, { type: 'array', bookType: 'xlsx' });
  return new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}
