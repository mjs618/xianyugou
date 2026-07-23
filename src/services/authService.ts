// API 认证服务 - 调用后端 /api/auth/* 端点（P0-1 修复）。
//
// 设计与 settingsService.ts 一致：薄封装 apiClient，便于测试 mock。
// - getTokenStatus：查询后端是否已配置 token（data/api.token 是否存在）
// - verifyToken：校验用户输入的 token 是否匹配后端持久化的 token
//
// 端点白名单：/api/auth/* 由后端中间件放行，无需 X-API-Token 头。
import { apiClient } from './apiClient';

export interface TokenStatus {
  /** 后端 data/api.token 是否已存在 */
  token_configured: boolean;
}

export interface VerifyTokenResponse {
  /** token 是否匹配后端持久化的值 */
  valid: boolean;
}

// 查询后端 token 配置状态（首次启动引导用）
export async function getTokenStatus(): Promise<TokenStatus> {
  return apiClient.get<TokenStatus>('/api/auth/token-status');
}

// 校验用户输入的 token 是否正确；正确则前端调用 setApiToken 持久化到 sessionStorage
export async function verifyToken(token: string): Promise<VerifyTokenResponse> {
  return apiClient.post<VerifyTokenResponse>('/api/auth/verify-token', { token });
}
