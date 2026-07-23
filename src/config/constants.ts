/**
 * 全局常量。
 *
 * 抽离散落在组件内的魔法数字，便于统一调整与文档化。
 */

/** 主轮询/提醒检查间隔（毫秒）：MainLayout 每 10 分钟检查一次提醒 */
export const REMINDER_CHECK_INTERVAL_MS = 10 * 60 * 1000;

/** 回到顶部按钮触发的滚动阈值（像素） */
export const SCROLL_TOP_THRESHOLD = 400;

/** 后端长轮询间隔（毫秒）：订单同步/邮件发送状态查询使用 */
export const BACKEND_POLL_INTERVAL_MS = 15_000;

/** 售后工单"待处理超时"小时数：超过即视为 overdue */
export const AFTER_SALES_PENDING_OVERDUE_HOURS = 24;

/** 售后工单"处理中超时"小时数：超过即视为 overdue */
export const AFTER_SALES_PROCESSING_OVERDUE_HOURS = 48;

/** 质保即将到期天数：剩余天数 ≤ 此值视为 urgent */
export const WARRANTY_URGENT_DAYS = 3;
