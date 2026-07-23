import { describe, it, expect } from 'vitest';
import dayjs from 'dayjs';
import { filterTransactions, TransactionFilterOptions } from '@/utils/transactionFilter';
import type { Transaction } from '@/types';

// ==================== 测试数据构造 ====================

/** 构造一条 Transaction，可覆盖字段 */
function makeTx(overrides: Partial<Transaction> & { id: number }): Transaction {
  return {
    customer_id: 1,
    product_name: '测试商品',
    sale_price: 100,
    cost_price: 50,
    profit: 50,
    trade_at: new Date('2026-07-10T10:00:00'),
    status: 'completed',
    warranty_days: 30,
    source_type: 'direct',
    channel: 'xianyu',
    attachments: [],
    version: 0,
    created_at: new Date('2026-07-10T10:00:00'),
    updated_at: new Date('2026-07-10T10:00:00'),
    ...overrides,
  };
}

/** 默认筛选选项：全部不筛选 */
function defaultOptions(overrides: Partial<TransactionFilterOptions> = {}): TransactionFilterOptions {
  return {
    statusFilter: 'all',
    channelFilter: 'all',
    keyword: '',
    dateRange: null,
    timeFilter: 'all',
    warrantyUrgentOnly: false,
    customers: new Map(),
    ...overrides,
  };
}

// 三渠道混合测试数据
const mixedTx: Transaction[] = [
  makeTx({ id: 1, channel: 'xianyu', product_name: '闲鱼商品A', xianyu_order_no: 'XY001', customer_id: 10, status: 'completed' }),
  makeTx({ id: 2, channel: 'xianyu', product_name: '闲鱼商品B', xianyu_order_no: 'XY002', customer_id: 11, status: 'pending' }),
  makeTx({ id: 3, channel: 'wechat', product_name: '微信商品C', customer_id: 12, status: 'completed' }),
  makeTx({ id: 4, channel: 'wechat', product_name: '微信商品D', customer_id: 13, status: 'aftersales' }),
  makeTx({ id: 5, channel: 'other', product_name: '其他渠道E', customer_id: 14, status: 'completed' }),
];

// ==================== 渠道筛选测试（核心） ====================

describe('filterTransactions - 渠道筛选', () => {
  describe('单一渠道筛选', () => {
    it('channelFilter="all" 返回全部交易（不筛选）', () => {
      const result = filterTransactions(mixedTx, defaultOptions({ channelFilter: 'all' }));
      expect(result).toHaveLength(5);
      expect(result.map((t) => t.id)).toEqual([1, 2, 3, 4, 5]);
    });

    it('channelFilter="xianyu" 只返回闲鱼交易', () => {
      const result = filterTransactions(mixedTx, defaultOptions({ channelFilter: 'xianyu' }));
      expect(result).toHaveLength(2);
      expect(result.every((t) => t.channel === 'xianyu')).toBe(true);
      expect(result.map((t) => t.id)).toEqual([1, 2]);
    });

    it('channelFilter="wechat" 只返回微信交易', () => {
      const result = filterTransactions(mixedTx, defaultOptions({ channelFilter: 'wechat' }));
      expect(result).toHaveLength(2);
      expect(result.every((t) => t.channel === 'wechat')).toBe(true);
      expect(result.map((t) => t.id)).toEqual([3, 4]);
    });

    it('channelFilter="other" 只返回其他渠道交易', () => {
      const result = filterTransactions(mixedTx, defaultOptions({ channelFilter: 'other' }));
      expect(result).toHaveLength(1);
      expect(result[0].channel).toBe('other');
      expect(result[0].id).toBe(5);
    });
  });

  describe('渠道筛选边界场景', () => {
    it('筛选不存在的渠道返回空数组', () => {
      // 所有交易都是 xianyu，筛 wechat 应为空
      const allXianyu = [
        makeTx({ id: 1, channel: 'xianyu' }),
        makeTx({ id: 2, channel: 'xianyu' }),
      ];
      const result = filterTransactions(allXianyu, defaultOptions({ channelFilter: 'wechat' }));
      expect(result).toHaveLength(0);
    });

    it('空数据集筛选任何渠道都返回空', () => {
      for (const ch of ['all', 'xianyu', 'wechat', 'other']) {
        const result = filterTransactions([], defaultOptions({ channelFilter: ch }));
        expect(result).toHaveLength(0);
      }
    });

    it('全部交易同一渠道，筛选该渠道返回全部', () => {
      const allWechat = [
        makeTx({ id: 1, channel: 'wechat' }),
        makeTx({ id: 2, channel: 'wechat' }),
        makeTx({ id: 3, channel: 'wechat' }),
      ];
      const result = filterTransactions(allWechat, defaultOptions({ channelFilter: 'wechat' }));
      expect(result).toHaveLength(3);
    });

    it('渠道筛选保持原始顺序（不重排）', () => {
      const data = [
        makeTx({ id: 10, channel: 'xianyu' }),
        makeTx({ id: 20, channel: 'wechat' }),
        makeTx({ id: 30, channel: 'xianyu' }),
        makeTx({ id: 40, channel: 'wechat' }),
      ];
      const result = filterTransactions(data, defaultOptions({ channelFilter: 'xianyu' }));
      expect(result.map((t) => t.id)).toEqual([10, 30]);

      const result2 = filterTransactions(data, defaultOptions({ channelFilter: 'wechat' }));
      expect(result2.map((t) => t.id)).toEqual([20, 40]);
    });

    it('三渠道各一条，分别筛选验证', () => {
      const data = [
        makeTx({ id: 1, channel: 'xianyu', product_name: 'X' }),
        makeTx({ id: 2, channel: 'wechat', product_name: 'W' }),
        makeTx({ id: 3, channel: 'other', product_name: 'O' }),
      ];
      expect(filterTransactions(data, defaultOptions({ channelFilter: 'xianyu' }))).toHaveLength(1);
      expect(filterTransactions(data, defaultOptions({ channelFilter: 'wechat' }))).toHaveLength(1);
      expect(filterTransactions(data, defaultOptions({ channelFilter: 'other' }))).toHaveLength(1);
    });
  });
});

// ==================== 渠道 + 其他筛选组合 ====================

describe('filterTransactions - 渠道 + 状态组合', () => {
  it('渠道=wechat + 状态=completed 只返回微信已完成交易', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'wechat',
      statusFilter: 'completed',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(3);
    expect(result[0].channel).toBe('wechat');
    expect(result[0].status).toBe('completed');
  });

  it('渠道=xianyu + 状态=pending 只返回闲鱼待发货交易', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      statusFilter: 'pending',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
  });

  it('渠道=other + 状态=aftersales 无匹配时返回空', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'other',
      statusFilter: 'aftersales',
    }));
    expect(result).toHaveLength(0);
  });

  it('渠道=wechat + 状态=all 返回微信全部状态交易', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'wechat',
      statusFilter: 'all',
    }));
    expect(result).toHaveLength(2);
  });
});

describe('filterTransactions - 渠道 + 关键词组合', () => {
  it('渠道=xianyu + 关键词匹配商品名', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      keyword: '商品A',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
    expect(result[0].product_name).toBe('闲鱼商品A');
  });

  it('渠道=wechat + 关键词匹配订单号（仅闲鱼有订单号）', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      keyword: 'XY002',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
    expect(result[0].xianyu_order_no).toBe('XY002');
  });

  it('渠道=wechat + 关键词匹配买家昵称', () => {
    const customers = new Map([
      [12, '微信买家小王'],
      [13, '张三'],
    ]);
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'wechat',
      keyword: '小王',
      customers,
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(3);
    expect(result[0].customer_id).toBe(12);
  });

  it('渠道=other + 关键词无匹配返回空', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'other',
      keyword: '不存在关键词',
    }));
    expect(result).toHaveLength(0);
  });

  it('关键词不区分大小写', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      keyword: 'xy001',  // 小写搜索
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });
});

describe('filterTransactions - 渠道 + 状态 + 关键词三重组合', () => {
  it('渠道=xianyu + 状态=completed + 关键词=商品A 精确命中一条', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      statusFilter: 'completed',
      keyword: '商品A',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('渠道=xianyu + 状态=completed + 关键词=商品B 无命中（商品B是pending）', () => {
    const result = filterTransactions(mixedTx, defaultOptions({
      channelFilter: 'xianyu',
      statusFilter: 'completed',
      keyword: '商品B',
    }));
    expect(result).toHaveLength(0);
  });
});

// ==================== 渠道 + 日期/时间组合 ====================

describe('filterTransactions - 渠道 + 日期范围组合', () => {
  it('渠道=xianyu + dateRange 命中范围内的交易', () => {
    const data = [
      makeTx({ id: 1, channel: 'xianyu', trade_at: new Date('2026-07-05') }),
      makeTx({ id: 2, channel: 'xianyu', trade_at: new Date('2026-07-15') }),
      makeTx({ id: 3, channel: 'wechat', trade_at: new Date('2026-07-10') }),
    ];
    const result = filterTransactions(data, defaultOptions({
      channelFilter: 'xianyu',
      dateRange: [dayjs('2026-07-01'), dayjs('2026-07-10')],
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });
});

describe('filterTransactions - 渠道 + 时间快捷筛选', () => {
  it('渠道=wechat + timeFilter=today 只返回今天微信交易', () => {
    const today = new Date();
    const data = [
      makeTx({ id: 1, channel: 'wechat', trade_at: today }),
      makeTx({ id: 2, channel: 'wechat', trade_at: new Date('2026-01-01') }),
      makeTx({ id: 3, channel: 'xianyu', trade_at: today }),
    ];
    const result = filterTransactions(data, defaultOptions({
      channelFilter: 'wechat',
      timeFilter: 'today',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('渠道=xianyu + timeFilter=week 只返回一周内闲鱼交易', () => {
    const now = new Date();
    const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);
    const tenDaysAgo = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000);
    const data = [
      makeTx({ id: 1, channel: 'xianyu', trade_at: threeDaysAgo }),
      makeTx({ id: 2, channel: 'xianyu', trade_at: tenDaysAgo }),
      makeTx({ id: 3, channel: 'wechat', trade_at: threeDaysAgo }),
    ];
    const result = filterTransactions(data, defaultOptions({
      channelFilter: 'xianyu',
      timeFilter: 'week',
    }));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });
});

// ==================== 默认选项回归 ====================

describe('filterTransactions - 默认选项回归', () => {
  it('全部默认选项返回原始数据（不筛选）', () => {
    const result = filterTransactions(mixedTx, defaultOptions());
    expect(result).toHaveLength(5);
    expect(result).toEqual(mixedTx);
  });

  it('空数组 + 默认选项返回空数组', () => {
    const result = filterTransactions([], defaultOptions());
    expect(result).toHaveLength(0);
  });
});
