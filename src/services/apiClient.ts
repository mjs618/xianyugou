// 统一 API Client - 封装与 FastAPI 后端的通信。
// 所有后端调用都经过这里，统一处理 baseURL、错误、JSON 序列化。
//
// 设计原则：
// - 与现有 mailService 的裸 fetch 风格保持一致（无新依赖）
// - 后端地址可通过 localStorage 覆盖（便于部署时配置）
// - 失败时抛出 Error，调用方用 try/catch 或 message.error 处理

// 后端地址：优先 localStorage 配置，其次默认本地开发地址
const BACKEND_KEY = 'xianyu-backend-url';
const DEFAULT_BACKEND = 'http://localhost:8000';

// 安全访问 localStorage（Node/SSR 等非浏览器环境降级）
function safeStorage(): Storage | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null;
  } catch {
    return null;
  }
}

export function getBackendUrl(): string {
  return safeStorage()?.getItem(BACKEND_KEY)?.trim() || DEFAULT_BACKEND;
}

export function setBackendUrl(url: string): void {
  const trimmed = url.trim().replace(/\/+$/, '');
  safeStorage()?.setItem(BACKEND_KEY, trimmed || DEFAULT_BACKEND);
}

// 后端返回的错误格式（FastAPI HTTPException）
export interface ApiError {
  detail: string;
  status: number;
}

export class ApiException extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.name = 'ApiException';
  }
}

// duck-typing 判断 API 错误 + 状态码。
// 不用 instanceof：mock 环境下抛出的错误可能是不同类实例，靠 name/status 判断更健壮。
export function isApiError(err: unknown, status?: number): boolean {
  if (!(err instanceof Error)) return false;
  const e = err as { name?: string; status?: number };
  if (e.name !== 'ApiException') return false;
  if (status !== undefined && e.status !== status) return false;
  return true;
}

// 检查后端是否在线
export async function checkBackend(): Promise<boolean> {
  try {
    const res = await fetch(`${getBackendUrl()}/api/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

// 通用请求方法
async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; params?: Record<string, string | number | boolean | undefined> } = {}
): Promise<T> {
  const { method = 'GET', body, params } = options;
  let url = `${getBackendUrl()}${path}`;
  if (params) {
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) search.append(k, String(v));
    }
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiException(0, '无法连接后端服务，请确认后端已启动（默认 http://localhost:8000）');
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = (data?.detail) || `请求失败（${res.status}）`;
    throw new ApiException(res.status, detail);
  }
  return data as T;
}

export const apiClient = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'GET', params }),
  post: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'POST', body, params }),
  put: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'PUT', body, params }),
  patch: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'PATCH', body, params }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
};
