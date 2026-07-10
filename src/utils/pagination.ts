export function getPageForRecordId<T extends { id?: number }>(
  records: T[],
  targetId: number,
  pageSize: number,
  currentPage = 1,
): number {
  if (!targetId || pageSize <= 0) return currentPage;

  const targetIndex = records.findIndex((record) => record.id === targetId);
  if (targetIndex < 0) return currentPage;

  return Math.floor(targetIndex / pageSize) + 1;
}

export function clampPageForRecordCount(recordCount: number, pageSize: number, currentPage: number): number {
  if (pageSize <= 0) return Math.max(1, currentPage);

  const maxPage = Math.max(1, Math.ceil(recordCount / pageSize));
  return Math.min(Math.max(1, currentPage), maxPage);
}
