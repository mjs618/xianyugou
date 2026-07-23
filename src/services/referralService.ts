// 推荐关系服务 - 数据层迁移第三批：走后端 API。
// 推荐树/排行/环检测/层级/被介绍人均由后端聚合。
import type { ReferralTreeNode, ReferrerRanking } from '@/types';
import { apiClient } from './apiClient';

// 获取以某客户为根的推荐树
export async function getReferralTree(rootCustomerId: number): Promise<ReferralTreeNode> {
  return apiClient.get<ReferralTreeNode>(`/api/referral/tree/${rootCustomerId}`);
}

// 介绍人排行
export async function getReferrerRankings(): Promise<ReferrerRanking[]> {
  return apiClient.get<ReferrerRanking[]>('/api/referral/rankings');
}

// 获取某介绍人的所有被介绍人 ID
export async function getIntroducedBy(referrerId: number): Promise<number[]> {
  const r = await apiClient.get<{ ids: number[] }>(`/api/referral/introduced-by/${referrerId}`);
  return r.ids;
}

// 检测建立 referrer→buyer 推荐关系是否会成环
export async function wouldCreateCycle(referrerId: number, buyerId: number): Promise<boolean> {
  const r = await apiClient.get<{ wouldCreateCycle: boolean }>('/api/referral/would-cycle', { referrer_id: referrerId, buyer_id: buyerId });
  return r.wouldCreateCycle;
}

// 计算某客户的推荐层级
export async function calcReferralLevel(buyerId: number): Promise<number> {
  const r = await apiClient.get<{ level: number }>(`/api/referral/level/${buyerId}`);
  return r.level;
}
