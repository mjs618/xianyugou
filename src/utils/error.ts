/**
 * 统一错误处理工具。
 *
 * 用法：
 * ```ts
 * try {
 *   await api.foo();
 * } catch (err: unknown) {
 *   if (isValidationError(err)) return; // antd 表单校验错误，不提示
 *   message.error(getErrorMessage(err));
 * }
 * ```
 *
 * 取代 `catch (err: any) { err?.message }` 模式，避免 any 滥用。
 *
 * 注意：ApiException 继承 Error，因此会被 `err instanceof Error` 命中。
 * 如需进一步区分 API 错误，使用 `isApiError(err)` from `@/services/apiClient`。
 */

/**
 * antd Form.validateFields() 抛出的校验错误对象。
 * 形如 `{ errorFields: [...], values: {...} }`，不是 Error 实例。
 */
export interface ValidationError {
  errorFields: unknown[];
  values: Record<string, unknown>;
}

/**
 * 判断错误是否为 antd 表单校验错误。
 */
export function isValidationError(err: unknown): err is ValidationError {
  return (
    err !== null &&
    typeof err === 'object' &&
    'errorFields' in err &&
    Array.isArray((err as { errorFields: unknown }).errorFields)
  );
}

/**
 * 从 unknown 类型的错误中提取人类可读的消息。
 *
 * 优先级：
 * 1. Error 实例（含 ApiException，因其继承 Error）
 * 2. 字符串
 * 3. 兜底文案
 */
export function getErrorMessage(err: unknown, fallback = '操作失败，请重试'): string {
  if (err instanceof Error) {
    return err.message || fallback;
  }
  if (typeof err === 'string' && err.trim()) {
    return err;
  }
  return fallback;
}
