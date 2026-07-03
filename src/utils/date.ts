import dayjs from 'dayjs';

// 日期格式化
export const formatDate = (date?: Date | string | null, fmt = 'YYYY-MM-DD'): string => {
  if (!date) return '-';
  return dayjs(date).format(fmt);
};

export const formatDateTime = (date?: Date | string | null): string => {
  if (!date) return '-';
  return dayjs(date).format('YYYY-MM-DD HH:mm');
};

// 获取本月起止
export const getMonthRange = (date = new Date()) => {
  const start = dayjs(date).startOf('month').toDate();
  const end = dayjs(date).endOf('month').toDate();
  return { start, end };
};

// 获取上月起止
export const getPrevMonthRange = (date = new Date()) => {
  const start = dayjs(date).subtract(1, 'month').startOf('month').toDate();
  const end = dayjs(date).subtract(1, 'month').endOf('month').toDate();
  return { start, end };
};

// 获取最近 N 天范围
export const getRecentDaysRange = (days: number) => {
  const end = new Date();
  const start = dayjs().subtract(days, 'day').startOf('day').toDate();
  return { start, end };
};

// 计算两日期相差天数（向上取整）
export const daysBetween = (end: Date, start: Date = new Date()): number => {
  const diffMs = new Date(end).getTime() - new Date(start).getTime();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
};

// 是否同一天
export const isSameDay = (a: Date, b: Date): boolean => {
  return dayjs(a).isSame(b, 'day');
};

// 生成日期序列（用于趋势图）
// 使用 YYYY-MM-DD 格式，避免跨年时不同年份同月日合并到同一点
export const dateSeries = (days: number): string[] => {
  const arr: string[] = [];
  for (let i = days - 1; i >= 0; i--) {
    arr.push(dayjs().subtract(i, 'day').format('YYYY-MM-DD'));
  }
  return arr;
};
