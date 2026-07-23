import { describe, expect, it } from 'vitest';
import { ApiException } from '@/services/apiClient';
import { getErrorMessage, isValidationError } from '@/utils/error';

describe('getErrorMessage', () => {
  it('Error 实例返回其 message', () => {
    const err = new Error('boom');
    expect(getErrorMessage(err)).toBe('boom');
  });

  it('ApiException（继承 Error）返回其 detail', () => {
    const err = new ApiException(500, '内部错误');
    expect(getErrorMessage(err)).toBe('内部错误');
  });

  it('ApiException 401 返回对应 detail', () => {
    const err = new ApiException(401, '未授权');
    expect(getErrorMessage(err)).toBe('未授权');
  });

  it('Error 实例 message 为空时返回 fallback', () => {
    const err = new Error('');
    expect(getErrorMessage(err, '默认文案')).toBe('默认文案');
  });

  it('字符串原样返回', () => {
    expect(getErrorMessage('网络错误')).toBe('网络错误');
  });

  it('空字符串返回 fallback', () => {
    expect(getErrorMessage('')).toBe('操作失败，请重试');
    expect(getErrorMessage('', '自定义')).toBe('自定义');
  });

  it('None / null 返回 fallback', () => {
    expect(getErrorMessage(null)).toBe('操作失败，请重试');
    expect(getErrorMessage(undefined)).toBe('操作失败，请重试');
  });

  it('数字返回 fallback', () => {
    expect(getErrorMessage(42)).toBe('操作失败，请重试');
  });

  it('对象返回 fallback', () => {
    expect(getErrorMessage({ foo: 'bar' })).toBe('操作失败，请重试');
  });

  it('使用自定义 fallback', () => {
    expect(getErrorMessage(null, '保存失败')).toBe('保存失败');
    expect(getErrorMessage(42, '保存失败')).toBe('保存失败');
  });
});

describe('isValidationError', () => {
  it('识别 antd 表单校验错误（含 errorFields 数组）', () => {
    const err = { errorFields: [{ name: ['foo'], errors: ['必填'] }], values: {} };
    expect(isValidationError(err)).toBe(true);
  });

  it('errorFields 为空数组也算校验错误', () => {
    const err = { errorFields: [], values: {} };
    expect(isValidationError(err)).toBe(true);
  });

  it('Error 实例不算校验错误', () => {
    const err = new Error('普通错误');
    expect(isValidationError(err)).toBe(false);
  });

  it('ApiException 不算校验错误', () => {
    const err = new ApiException(500, '内部错误');
    expect(isValidationError(err)).toBe(false);
  });

  it('errorFields 不是数组不算校验错误', () => {
    const err = { errorFields: 'not-an-array', values: {} };
    expect(isValidationError(err)).toBe(false);
  });

  it('null 不算校验错误', () => {
    expect(isValidationError(null)).toBe(false);
  });

  it('undefined 不算校验错误', () => {
    expect(isValidationError(undefined)).toBe(false);
  });

  it('字符串不算校验错误', () => {
    expect(isValidationError('some error')).toBe(false);
  });

  it('识别为校验错误后可作为类型守卫访问 errorFields', () => {
    const err: unknown = { errorFields: [{ name: ['x'], errors: ['err'] }], values: {} };
    if (isValidationError(err)) {
      expect(err.errorFields).toHaveLength(1);
      expect(err.values).toEqual({});
    } else {
      throw new Error('should be ValidationError');
    }
  });
});
