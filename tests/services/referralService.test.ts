import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import { getReferralTree, getReferrerRankings, wouldCreateCycle, calcReferralLevel, getIntroducedBy, createReferralAndRebate } from '@/services/referralService';

describe('referralService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('getReferralTree 应 GET /api/referral/tree/{id}', async () => {
    setMockResponse('get', '/api/referral/tree/1', {
      id: 1, name: 'A', level: 0, totalRevenue: 500,
      children: [{ id: 2, name: 'B', level: 1, totalRevenue: 200, children: [] }],
    });
    const tree = await getReferralTree(1);
    expect(tree.name).toBe('A');
    expect(tree.children.length).toBe(1);
    expect(tree.children[0].name).toBe('B');
  });

  it('getReferrerRankings 应 GET /api/referral/rankings', async () => {
    setMockResponse('get', '/api/referral/rankings', [
      { referrerId: 1, nickname: 'A', introducedCount: 3, broughtRevenue: 1000, paidRebate: 50, pendingRebate: 20 },
    ]);
    const r = await getReferrerRankings();
    expect(r[0].nickname).toBe('A');
    expect(r[0].introducedCount).toBe(3);
  });

  it('wouldCreateCycle 应传递 referrer_id/buyer_id 并返回布尔', async () => {
    setMockResponse('get', '/api/referral/would-cycle', { wouldCreateCycle: true }, { referrer_id: 2, buyer_id: 1 });
    expect(await wouldCreateCycle(2, 1)).toBe(true);
    const params = getMockCalls('get', '/api/referral/would-cycle')[0].params as any;
    expect(params.referrer_id).toBe(2);
    expect(params.buyer_id).toBe(1);
  });

  it('calcReferralLevel 应 GET /api/referral/level/{id}', async () => {
    setMockResponse('get', '/api/referral/level/3', { level: 2 });
    expect(await calcReferralLevel(3)).toBe(2);
  });

  it('getIntroducedBy 应返回被介绍人 ID 数组', async () => {
    setMockResponse('get', '/api/referral/introduced-by/1', { ids: [2, 3, 4] });
    expect(await getIntroducedBy(1)).toEqual([2, 3, 4]);
  });

  it('createReferralAndRebate 应为 no-op（后端 create_transaction 内联处理）', async () => {
    await expect(createReferralAndRebate({
      referrerId: 1, buyerId: 2, transactionId: 1, profit: 100, salePrice: 200,
    })).resolves.toBeUndefined();
  });
});
