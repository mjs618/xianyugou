// mock apiClient 基建 - 供迁移后的 service 测试使用。
//
// 用法（每个测试文件顶部）：
//   vi.mock('@/services/apiClient', () => mockApiFactory());
//   import { ... } from '@/services/...';  // 必须在 vi.mock 之后
//
// 原理：vi.mock 工厂会被提升到文件顶部，普通变量在提升时未初始化。
// 用 vi.hoisted 把整个 mock 实现（state + execute + factory）提升，
// 保证工厂执行时所有依赖已就绪。
import { vi } from 'vitest';

const mocked = vi.hoisted(() => {
  // 提升的 mock 状态（模块级单例，所有测试共享）
  const calls: Record<string, Record<string, any[]>> = {};
  const responses: Record<string, Record<string, any>> = {};

  function key(path: string, params?: Record<string, unknown>): string {
    if (params && Object.keys(params).length > 0) {
      return path + '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v as any)]),
      ).toString();
    }
    return path;
  }

  function execute(method: string, path: string, body?: unknown, params?: Record<string, unknown>): Promise<any> {
    if (!calls[method]) calls[method] = {};
    if (!calls[method][path]) calls[method][path] = [];
    calls[method][path].push({ body, params });

    if (!responses[method]) responses[method] = {};
    let resp = responses[method][key(path, params)];
    if (resp === undefined) resp = responses[method][path];
    if (resp === undefined) {
      return Promise.reject(new Error(`mock 未设置响应：${method.toUpperCase()} ${path}`));
    }
    if (resp && typeof resp === 'object' && resp.__error) {
      // 构造带 status 的错误对象（service 用 instanceof ApiException / .status 判断）
      const err: any = new Error(resp.detail);
      err.status = resp.status;
      err.name = 'ApiException';
      return Promise.reject(err);
    }
    return Promise.resolve(resp);
  }

  // ApiException 类（提升作用域内定义，保证 instanceof 一致）
  class ApiException extends Error {
    status: number;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.name = 'ApiException';
    }
  }

  // vi.mock 工厂
  function mockApiFactory() {
    return {
      apiClient: {
        get: (path: string, params?: Record<string, unknown>) => execute('get', path, undefined, params),
        post: (path: string, body?: unknown, params?: Record<string, unknown>) => execute('post', path, body, params),
        put: (path: string, body?: unknown, params?: Record<string, unknown>) => execute('put', path, body, params),
        patch: (path: string, body?: unknown, params?: Record<string, unknown>) => execute('patch', path, body, params),
        delete: (path: string) => execute('delete', path),
      },
      ApiException,
      // isApiError 复刻：与 src/services/apiClient.ts 的 duck-typing 一致，
      // 保证 service 的错误判断在 mock 下也成立
      isApiError: (err: unknown, status?: number): boolean => {
        if (!(err instanceof Error)) return false;
        const e = err as { name?: string; status?: number };
        if (e.name !== 'ApiException') return false;
        if (status !== undefined && e.status !== status) return false;
        return true;
      },
      checkBackend: () => Promise.resolve(true),
      getBackendUrl: () => 'http://localhost:8000',
      setBackendUrl: () => {},
    };
  }

  return { calls, responses, mockApiFactory };
});

// 导出工厂（供 vi.mock 使用，提升安全）
export const mockApiFactory = mocked.mockApiFactory;

// 导出配置/断言 helper（这些在测试用例里调用，模块求值时已就绪，无需提升）
export function resetMockApi(): void {
  for (const k of Object.keys(mocked.calls)) delete mocked.calls[k];
  for (const k of Object.keys(mocked.responses)) delete mocked.responses[k];
}

export function setMockResponse(
  method: string,
  path: string,
  response: unknown,
  params?: Record<string, unknown>,
): void {
  if (!mocked.responses[method]) mocked.responses[method] = {};
  const k = params && Object.keys(params).length
    ? path + '?' + new URLSearchParams(Object.entries(params).map(([kk, v]) => [kk, String(v as any)])).toString()
    : path;
  mocked.responses[method][k] = response;
}

export function setMockError(
  method: string,
  path: string,
  status: number,
  detail: string,
  params?: Record<string, unknown>,
): void {
  setMockResponse(method, path, { __error: true, status, detail }, params);
}

export function getMockCalls(
  method: string,
  path: string,
): { body?: unknown; params?: Record<string, unknown> }[] {
  return mocked.calls[method]?.[path] || [];
}
