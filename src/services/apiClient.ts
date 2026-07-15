// 统一 API Client - 封装与 FastAPI 后端的通信。
// 所有后端调用都经过这里，统一处理 baseURL、错误、JSON 序列化。
//
// 设计原则：
// - 与现有 mailService 的裸 fetch 风格保持一致（无新依赖）
// - 后端地址可通过 localStorage 覆盖（便于部署时配置）
// - 失败时抛出 Error，调用方用 try/catch 或 message.error 处理
// - 携带预共享 API Token（P0-1 修复），从 sessionStorage 读取

// 后端地址：优先 localStorage 配置，其次默认本地开发地址
const BACKEND_KEY = 'xianyu-backend-url';
const BUILD_BACKEND = import.meta.env.VITE_BACKEND_URL?.trim();
const DEFAULT_BACKEND = (BUILD_BACKEND || 'http://localhost:18001').replace(/\/+$/, '');

// API Token：存 sessionStorage 而非 localStorage（会话级，关闭浏览器即清除，更安全）
const TOKEN_KEY = 'xianyu-api-token';
const authRequiredListeners = new Set<() => void>();

// 安全访问 localStorage（Node/SSR 等非浏览器环境降级）
function safeStorage(storage: 'local' | 'session'): Storage | null {
  try {
    if (storage === 'local') {
      return typeof localStorage !== 'undefined' ? localStorage : null;
    }
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null;
  } catch {
    return null;
  }
}

export function getBackendUrl(): string {
  return safeStorage('local')?.getItem(BACKEND_KEY)?.trim() || DEFAULT_BACKEND;
}

export function getApiUrl(path: string): string {
  return `${getBackendUrl()}${path}`;
}

export function setBackendUrl(url: string): void {
  const trimmed = url.trim().replace(/\/+$/, '');
  safeStorage('local')?.setItem(BACKEND_KEY, trimmed || DEFAULT_BACKEND);
}

// ===== API Token 存取 =====
export function getApiToken(): string | null {
  return safeStorage('session')?.getItem(TOKEN_KEY)?.trim() || null;
}

export function setApiToken(token: string): void {
  const trimmed = token.trim();
  if (trimmed) {
    safeStorage('session')?.setItem(TOKEN_KEY, trimmed);
  } else {
    safeStorage('session')?.removeItem(TOKEN_KEY);
  }
}

export function clearApiToken(): void {
  safeStorage('session')?.removeItem(TOKEN_KEY);
}

export function hasApiToken(): boolean {
  return !!getApiToken();
}

export function subscribeAuthRequired(listener: () => void): () => void {
  authRequiredListeners.add(listener);
  return () => authRequiredListeners.delete(listener);
}

function notifyAuthRequired(): void {
  authRequiredListeners.forEach((listener) => listener());
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

// 默认请求超时（毫秒）。长任务（同步、导入）可用 apiClient.getLong/postLong 覆盖。
const DEFAULT_TIMEOUT_MS = 15_000;
// 长任务默认超时（毫秒）：同步、导入导出等可能耗时较长。
const LONG_TIMEOUT_MS = 60_000;
// 重试间隔（毫秒）
const RETRY_DELAY_MS = 500;

// 通用请求方法
async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    params?: Record<string, string | number | boolean | undefined>;
    timeoutMs?: number;      // P2-4：可配置超时（默认 15s）
    retry?: boolean;         // P2-4：是否启用重试（默认 true，POST 等长任务应显式关闭）
  } = {}
): Promise<T> {
  const {
    method = 'GET',
    body,
    params,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    retry = true,
  } = options;
  let url = `${getBackendUrl()}${path}`;
  if (params) {
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) search.append(k, String(v));
    }
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const buildInit = (): RequestInit => {
    const init: RequestInit = { method };
    // 注入预共享 API Token（P0-1 修复）
    const token = getApiToken();
    if (token) {
      init.headers = { ...(init.headers as Record<string, string> || {}), 'X-API-Token': token };
    }
    if (body !== undefined) {
      if (body instanceof FormData) {
        init.body = body;
      } else {
        init.headers = { ...(init.headers as Record<string, string> || {}), 'Content-Type': 'application/json' };
        init.body = JSON.stringify(body);
      }
    }
    return init;
  };

  // 单次请求（含超时控制）
  const fetchOnce = (): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, { ...buildInit(), signal: controller.signal })
      .finally(() => clearTimeout(timer));
  };

  // 判断是否可重试：网络错误（fetch reject）或 5xx / 429
  // 4xx（除 429）不重试：客户端错误重试也无效
  // 超时（AbortError）不重试：避免重复执行可能已部分处理的请求
  const isRetryableStatus = (status: number): boolean => status >= 500 || status === 429;

  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

  let res: Response;
  try {
    res = await fetchOnce();
    // 5xx / 429：尝试重试一次（除非调用方关闭 retry）
    if (retry && isRetryableStatus(res.status)) {
      await sleep(RETRY_DELAY_MS);
      res = await fetchOnce();
    }
  } catch (err) {
    // 超时（AbortError）：不重试，直接抛超时错误
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiException(0, `请求超时（${timeoutMs}ms），请稍后重试`);
    }
    // 网络错误：重试一次（除非 retry=false）
    if (retry) {
      await sleep(RETRY_DELAY_MS);
      try {
        res = await fetchOnce();
      } catch {
        throw new ApiException(0, `无法连接后端服务，请确认后端已启动（默认 ${DEFAULT_BACKEND}）`);
      }
    } else {
      throw new ApiException(0, `无法连接后端服务，请确认后端已启动（默认 ${DEFAULT_BACKEND}）`);
    }
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail = (data?.detail) || `请求失败（${res.status}）`;
    // 401 时给出更明确的提示，引导用户去 Settings 配置 token
    if (res.status === 401) {
      clearApiToken();
      notifyAuthRequired();
      throw new ApiException(401, '后端要求认证：请在「设置 → API 安全」中配置 API Token');
    }
    throw new ApiException(res.status, detail);
  }
  return data as T;
}

export const apiClient = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'GET', params }),
  // 长任务专用：超时 60s（适用于同步、导出等可能耗时较长的 GET 请求）
  getLong: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'GET', params, timeoutMs: LONG_TIMEOUT_MS }),
  post: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'POST', body, params }),
  // 长任务专用 POST：超时 60s + 关闭重试（避免重复执行可能有副作用的写操作）
  postLong: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body, timeoutMs: LONG_TIMEOUT_MS, retry: false }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'PUT', body, params }),
  patch: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>(path, { method: 'PATCH', body, params }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
};
