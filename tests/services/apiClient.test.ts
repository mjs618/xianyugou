// P2-4 前端 fetch 超时 + 重试策略测试
//
// 测试对象：src/services/apiClient.ts 中的 request 函数（通过 apiClient 公共方法间接调用）
// 测试重点：
//   - 默认 15s 超时（AbortController）
//   - 5xx / 429 → 重试一次
//   - 网络错误（fetch reject）→ 重试一次
//   - 4xx（除 429）→ 不重试
//   - 超时（AbortError）→ 不重试
//   - postLong → 关闭重试 + 60s 超时
//
// 使用 fake timers 控制：
//   - RETRY_DELAY_MS（500ms）的重试延迟
//   - DEFAULT_TIMEOUT_MS（15000ms）的 AbortController 超时
//
// 重要：对于会 reject 的测试，必须在 advanceTimersByTimeAsync 之前
// 附加 rejection handler（用 expect(promise).rejects.toMatchObject(...)），
// 否则 Node 会报 PromiseRejectionHandledWarning（rejection 在 handler 附加前已触发）。

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  apiClient,
  ApiException,
  getApiToken,
  setApiToken,
  subscribeAuthRequired,
} from '@/services/apiClient';

// 构造 mock Response 对象
function makeResponse(body: unknown, status = 200): Response {
  const text = body === undefined || body === null ? '' : JSON.stringify(body);
  return {
    status,
    ok: status >= 200 && status < 300,
    text: () => Promise.resolve(text),
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

// 构造网络错误（fetch reject 时抛出）
function networkError(): Error {
  return new TypeError('Failed to fetch');
}

describe('apiClient P2-4：超时 + 重试', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // ===== 基础请求行为 =====

  it('成功请求返回 JSON 数据', async () => {
    fetchMock.mockResolvedValue(makeResponse({ ok: true, data: 'hello' }));
    const result = await apiClient.get('/api/test');
    expect(result).toEqual({ ok: true, data: 'hello' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('204 No Content 返回 undefined', async () => {
    fetchMock.mockResolvedValue(makeResponse(undefined, 204));
    const result = await apiClient.delete('/api/test/1');
    expect(result).toBeUndefined();
  });

  it('POST 请求正确序列化 JSON body', async () => {
    fetchMock.mockResolvedValue(makeResponse({ ok: true }));
    await apiClient.post('/api/create', { name: 'test', value: 42 });
    const [, init] = fetchMock.mock.calls[0];
    const requestInit = init as RequestInit;
    expect(requestInit.method).toBe('POST');
    expect(requestInit.body).toBe(JSON.stringify({ name: 'test', value: 42 }));
    const headers = requestInit.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });

  // ===== 4xx 不重试 =====

  it('404 不重试，直接抛 ApiException(404)', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'Not Found' }, 404));
    await expect(apiClient.get('/api/missing')).rejects.toMatchObject({
      name: 'ApiException',
      status: 404,
      message: 'Not Found',
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('401 给出 API Token 配置提示', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'Unauthorized' }, 401));
    await expect(apiClient.get('/api/protected')).rejects.toMatchObject({
      name: 'ApiException',
      status: 401,
      message: /API Token/,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('401 清除失效 Token 并通知认证入口', async () => {
    const values = new Map<string, string>();
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    });
    const listener = vi.fn();
    const unsubscribe = subscribeAuthRequired(listener);
    setApiToken('expired-token');
    fetchMock.mockResolvedValue(makeResponse({ detail: 'Unauthorized' }, 401));

    await expect(apiClient.get('/api/protected')).rejects.toMatchObject({ status: 401 });

    expect(getApiToken()).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  // ===== 5xx / 429 重试一次 =====

  it('503 重试一次，重试成功', async () => {
    fetchMock
      .mockResolvedValueOnce(makeResponse({ detail: 'Server Error' }, 503))
      .mockResolvedValueOnce(makeResponse({ ok: true }));
    const promise = apiClient.get('/api/flaky');
    // 推进 500ms 重试延迟
    await vi.advanceTimersByTimeAsync(500);
    const result = await promise;
    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('429 触发重试一次', async () => {
    fetchMock
      .mockResolvedValueOnce(makeResponse({ detail: 'Too Many' }, 429))
      .mockResolvedValueOnce(makeResponse({ ok: true }));
    const promise = apiClient.get('/api/rate-limited');
    await vi.advanceTimersByTimeAsync(500);
    const result = await promise;
    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('5xx 重试仍为 5xx，抛 ApiException(503)', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'Still Down' }, 503));
    const promise = apiClient.get('/api/always-503');
    // 先附加 rejection handler，避免 timer 推进期间 rejection 无人处理
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 503,
      message: 'Still Down',
    });
    await vi.advanceTimersByTimeAsync(500);
    await assertion;
    // 一次原始 + 一次重试 = 2 次
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  // ===== 网络错误重试 =====

  it('网络错误重试一次，重试成功', async () => {
    fetchMock
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce(makeResponse({ ok: true }));
    const promise = apiClient.get('/api/down');
    await vi.advanceTimersByTimeAsync(500);
    const result = await promise;
    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('网络错误重试仍失败，抛 ApiException(status=0)', async () => {
    fetchMock.mockRejectedValue(networkError());
    const promise = apiClient.get('/api/always-down');
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 0,
    });
    await vi.advanceTimersByTimeAsync(500);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  // ===== postLong：关闭重试 + 60s 超时 =====

  it('postLong 网络错误不重试，只调用一次 fetch', async () => {
    fetchMock.mockRejectedValue(networkError());
    const promise = apiClient.postLong('/api/sync', { foo: 'bar' });
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 0,
    });
    // 即使推进时间也不应重试
    await vi.advanceTimersByTimeAsync(2000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('postLong 5xx 不重试', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'Server Error' }, 500));
    const promise = apiClient.postLong('/api/long-write', { data: 'test' });
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 500,
    });
    await vi.advanceTimersByTimeAsync(2000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  // ===== 超时控制（AbortController） =====

  it('默认 15s 超时：fetch 不返回时抛 ApiException(0, 超时)', async () => {
    // mock fetch 永不主动 resolve，等待 abort signal 触发
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        if (signal.aborted) {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
          return;
        }
        signal.addEventListener('abort', () => {
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });
    const promise = apiClient.get('/api/slow');
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 0,
      message: /超时/,
    });
    // 推进 15s 触发 AbortController 超时
    await vi.advanceTimersByTimeAsync(15000);
    await assertion;
    // 超时不重试
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('getLong 使用 60s 超时，15s 不触发超时', async () => {
    let abortFired = false;
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        const signal = init.signal as AbortSignal;
        signal.addEventListener('abort', () => {
          abortFired = true;
          const err = new Error('aborted');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });
    const promise = apiClient.getLong('/api/long-poll');
    const assertion = expect(promise).rejects.toMatchObject({
      name: 'ApiException',
      status: 0,
      message: /超时/,
    });
    // 推进 15s — 默认超时点，getLong 不应超时
    await vi.advanceTimersByTimeAsync(15000);
    expect(abortFired).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    // 推进剩余 45s（总计 60s）— getLong 超时
    await vi.advanceTimersByTimeAsync(45000);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  // ===== AbortSignal 传入验证 =====

  it('fetch 调用传入 AbortSignal', async () => {
    fetchMock.mockResolvedValue(makeResponse({ ok: true }));
    await apiClient.get('/api/with-signal');
    const callInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(callInit.signal).toBeTruthy();
    expect(typeof (callInit.signal as AbortSignal).addEventListener).toBe('function');
  });

  it('POST 请求也传入 AbortSignal', async () => {
    fetchMock.mockResolvedValue(makeResponse({ ok: true }));
    await apiClient.post('/api/create', { x: 1 });
    const callInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(callInit.signal).toBeTruthy();
  });

  // ===== ApiException 类型 =====

  it('ApiException 是 Error 子类且携带 status', async () => {
    fetchMock.mockResolvedValue(makeResponse({ detail: 'fail' }, 500));
    const promise = apiClient.get('/api/fail');
    // 先附加 handler，避免 timer 推进期间 unhandled rejection
    let caught: ApiException | null = null;
    promise.catch((e) => { caught = e; });
    await vi.advanceTimersByTimeAsync(500);
    // 等待 microtask flush
    await Promise.resolve();
    expect(caught).not.toBeNull();
    expect(caught).toBeInstanceOf(Error);
    expect(caught).toBeInstanceOf(ApiException);
    expect(caught!.status).toBe(500);
  });
});
