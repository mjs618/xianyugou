import { describe, expect, it } from 'vitest';
import { shouldBlockNavigation } from '@/hooks/useUnsavedChanges';

describe('shouldBlockNavigation', () => {
  it.each([
    [{ dirty: true, submitting: false, allowNavigation: false }, true],
    [{ dirty: false, submitting: false, allowNavigation: false }, false],
    [{ dirty: true, submitting: true, allowNavigation: false }, false],
    [{ dirty: true, submitting: false, allowNavigation: true }, false],
  ])('根据表单状态决定是否阻止离开 %#', (state, expected) => {
    expect(shouldBlockNavigation(state)).toBe(expected);
  });
});
