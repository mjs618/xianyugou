import { describe, expect, it } from 'vitest';
import { clampPageForRecordCount, getPageForRecordId } from '@/utils/pagination';

const records = Array.from({ length: 25 }, (_, index) => ({ id: index + 1 }));

describe('pagination', () => {
  it('根据目标记录 ID 计算所在页码', () => {
    expect(getPageForRecordId(records, 1, 20)).toBe(1);
    expect(getPageForRecordId(records, 20, 20)).toBe(1);
    expect(getPageForRecordId(records, 21, 20)).toBe(2);
  });

  it('目标不存在或参数无效时返回当前页码', () => {
    expect(getPageForRecordId(records, 99, 20, 3)).toBe(3);
    expect(getPageForRecordId(records, 21, 0, 3)).toBe(3);
    expect(getPageForRecordId(records, 0, 20, 3)).toBe(3);
  });

  it('数据缩小后把当前页码校正到有效页', () => {
    expect(clampPageForRecordCount(25, 20, 2)).toBe(2);
    expect(clampPageForRecordCount(19, 20, 2)).toBe(1);
    expect(clampPageForRecordCount(0, 20, 2)).toBe(1);
  });
});
