/**
 * P1-5 修复：通知轮询指数退避策略常量与计算。
 *
 * 抽成纯 TS 模块（不依赖 JSX）便于在 vitest node 环境下测试。
 * NotificationCenter 组件 import 此模块并驱动 setTimeout 递归调度。
 */

/** 30 秒：有未读或面板打开时的快速刷新间隔 */
export const MIN_INTERVAL = 30 * 1000;

/** 5 分钟：退避上限 */
export const MAX_INTERVAL = 300 * 1000;

/** 60 秒：无未读时的初始间隔 */
export const BASE_INTERVAL = 60 * 1000;

/**
 * 计算下次轮询间隔（纯函数，便于单测）。
 *
 * - 失败：拉长退避（×2），封顶 MAX_INTERVAL
 * - 成功 + 有未读/面板打开：固定 MIN_INTERVAL
 * - 成功 + 无未读：缓步退避（×1.5），下限 MIN_INTERVAL，上限 MAX_INTERVAL
 */
export function computeNextInterval(
  currentInterval: number,
  hasUnread: boolean,
  notifOpen: boolean,
  failed: boolean
): number {
  if (failed) {
    return Math.min(currentInterval * 2, MAX_INTERVAL);
  }
  if (notifOpen || hasUnread) {
    return MIN_INTERVAL;
  }
  const next = Math.min(Math.round(currentInterval * 1.5), MAX_INTERVAL);
  return Math.max(next, MIN_INTERVAL);
}
