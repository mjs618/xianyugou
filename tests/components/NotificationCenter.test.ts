/**
 * P1-5 修复验证：通知轮询指数退避策略的纯函数测试。
 *
 * 覆盖 computeNextInterval 的所有分支：
 * 1. 有未读 → 固定 MIN_INTERVAL
 * 2. 面板打开 → 固定 MIN_INTERVAL
 * 3. 失败 → ×2 退避，封顶 MAX_INTERVAL
 * 4. 成功 + 无未读 → ×1.5 缓步退避
 * 5. 退避达到 MAX_INTERVAL 后不再增长
 * 6. 退避不低于 MIN_INTERVAL（小于时被拉回到 MIN_INTERVAL）
 */
import { describe, expect, it } from 'vitest';
import {
  BASE_INTERVAL,
  MAX_INTERVAL,
  MIN_INTERVAL,
  computeNextInterval,
} from '@/utils/notificationPolling';

describe('NotificationCenter computeNextInterval', () => {
  describe('成功且有未读/面板打开时', () => {
    it('有未读时返回 MIN_INTERVAL', () => {
      expect(computeNextInterval(BASE_INTERVAL, true, false, false)).toBe(MIN_INTERVAL);
    });

    it('面板打开时返回 MIN_INTERVAL，即使无未读', () => {
      expect(computeNextInterval(BASE_INTERVAL, false, true, false)).toBe(MIN_INTERVAL);
    });

    it('有未读且面板打开时返回 MIN_INTERVAL', () => {
      expect(computeNextInterval(MAX_INTERVAL, true, true, false)).toBe(MIN_INTERVAL);
    });

    it('无论当前 interval 多大，有未读时都重置为 MIN_INTERVAL', () => {
      // 即便已退避到 MAX，有未读时应立即缩短
      expect(computeNextInterval(MAX_INTERVAL, true, false, false)).toBe(MIN_INTERVAL);
    });
  });

  describe('失败时拉长退避', () => {
    it('失败时 ×2，未达上限', () => {
      expect(computeNextInterval(BASE_INTERVAL, false, false, true)).toBe(BASE_INTERVAL * 2);
    });

    it('失败时 ×2，达到上限后封顶 MAX_INTERVAL', () => {
      // 当前 200s 失败 → 400s，但封顶 300s
      const current = 200_000;
      expect(computeNextInterval(current, false, false, true)).toBe(MAX_INTERVAL);
    });

    it('已在 MAX_INTERVAL 时失败不再增长', () => {
      expect(computeNextInterval(MAX_INTERVAL, false, false, true)).toBe(MAX_INTERVAL);
    });

    it('失败时即使有未读也走 ×2 退避（失败优先级最高）', () => {
      // 失败比有未读更优先：失败时退避拉长，避免雪崩
      expect(computeNextInterval(BASE_INTERVAL, true, false, true)).toBe(BASE_INTERVAL * 2);
    });
  });

  describe('成功且无未读时缓步退避', () => {
    it('BASE_INTERVAL 60s → 90s', () => {
      expect(computeNextInterval(BASE_INTERVAL, false, false, false)).toBe(90_000);
    });

    it('90s → 135s', () => {
      expect(computeNextInterval(90_000, false, false, false)).toBe(135_000);
    });

    it('135s → 202s (round(135 * 1.5) = 202)', () => {
      expect(computeNextInterval(135_000, false, false, false)).toBe(202_500);
    });

    it('缓步退避达到 MAX_INTERVAL 后封顶', () => {
      // 200s → round(200*1.5)=300s，正好等于 MAX
      expect(computeNextInterval(200_000, false, false, false)).toBe(MAX_INTERVAL);
      // 250s → round(250*1.5)=375s，封顶 300s
      expect(computeNextInterval(250_000, false, false, false)).toBe(MAX_INTERVAL);
    });

    it('已在 MAX_INTERVAL 时不再增长', () => {
      expect(computeNextInterval(MAX_INTERVAL, false, false, false)).toBe(MAX_INTERVAL);
    });
  });

  describe('MIN_INTERVAL 下限保护', () => {
    it('当前 interval 小于 MIN_INTERVAL 时被拉回到 MIN_INTERVAL', () => {
      // 假设异常情况下 currentInterval 为 10s（低于 MIN 30s）
      // 退避后 round(10*1.5)=15s，但应被拉回 30s
      expect(computeNextInterval(10_000, false, false, false)).toBe(MIN_INTERVAL);
    });
  });

  describe('常量取值', () => {
    it('MIN_INTERVAL 为 30 秒', () => {
      expect(MIN_INTERVAL).toBe(30_000);
    });

    it('MAX_INTERVAL 为 300 秒（5 分钟）', () => {
      expect(MAX_INTERVAL).toBe(300_000);
    });

    it('BASE_INTERVAL 为 60 秒', () => {
      expect(BASE_INTERVAL).toBe(60_000);
    });
  });

  describe('退避序列端到端验证', () => {
    it('无未读场景下连续 10 次成功后退避序列符合预期', () => {
      // 模拟连续 10 次成功 tick（无未读、面板关闭）
      let current = BASE_INTERVAL;
      const sequence: number[] = [];
      for (let i = 0; i < 10; i++) {
        current = computeNextInterval(current, false, false, false);
        sequence.push(current);
      }
      // 60 → 90 → 135 → 202(202500) → 303750→封顶 300 → 300 → 300...
      expect(sequence[0]).toBe(90_000);
      expect(sequence[1]).toBe(135_000);
      expect(sequence[2]).toBe(202_500);
      // 第 4 次开始封顶到 MAX_INTERVAL
      expect(sequence[3]).toBe(MAX_INTERVAL);
      // 之后稳定在 MAX_INTERVAL
      expect(sequence[9]).toBe(MAX_INTERVAL);
    });

    it('退避过程中途出现未读，立即缩短到 MIN_INTERVAL', () => {
      // 60 → 90 → 135 → 突然有未读 → 30
      let current = BASE_INTERVAL;
      current = computeNextInterval(current, false, false, false);
      expect(current).toBe(90_000);
      current = computeNextInterval(current, false, false, false);
      expect(current).toBe(135_000);
      // 第 3 次出现未读
      current = computeNextInterval(current, true, false, false);
      expect(current).toBe(MIN_INTERVAL);
    });

    it('退避过程中途失败，立即 ×2', () => {
      let current = BASE_INTERVAL;
      current = computeNextInterval(current, false, false, false);  // 90s
      // 失败
      current = computeNextInterval(current, false, false, true);
      expect(current).toBe(180_000);  // 90 * 2
      // 再次失败
      current = computeNextInterval(current, false, false, true);
      expect(current).toBe(MAX_INTERVAL);  // 360s 封顶 300s
    });
  });
});
