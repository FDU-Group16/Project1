import type { LocationQuery } from 'vue-router';

export interface SearchFilters {
  date: string;
  start: string;
  end: string;
  socket: boolean;
}

export const startHours = Array.from({ length: 24 }, (_, index) => String(index));
export const endHours = Array.from({ length: 24 }, (_, index) => String(index + 1));
export const hourLabel = (hour: string | number) => `${String(hour).padStart(2, '0')}:00`;

export function beijingDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const part = (name: string) => parts.find((entry) => entry.type === name)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function filtersFromQuery(query: LocationQuery): SearchFilters {
  const stringValue = (key: string, fallback: string) => typeof query[key] === 'string' ? query[key] : fallback;
  return {
    date: stringValue('date', beijingDate()),
    start: stringValue('start', '18'),
    end: stringValue('end', '20'),
    socket: query.socket === '1',
  };
}

export function filtersToQuery(filters: SearchFilters) {
  return { date: filters.date, start: filters.start, end: filters.end, socket: filters.socket ? '1' : '0' };
}

export function validateFilters(filters: SearchFilters, maxHours = 4): { date?: string; time?: string } {
  const errors: { date?: string; time?: string } = {};
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(filters.date)
    && !Number.isNaN(Date.parse(`${filters.date}T00:00:00+08:00`))
    && beijingDate(new Date(`${filters.date}T00:00:00+08:00`)) === filters.date;
  if (!validDate) errors.date = '请选择有效的预约日期。';
  else if (filters.date < beijingDate()) errors.date = '请选择今天或之后的日期。';

  if (!startHours.includes(filters.start) || !endHours.includes(filters.end)) {
    errors.time = '请选择列表中的整点时间。';
  } else if (Number(filters.end) <= Number(filters.start)) {
    errors.time = '结束时间需要晚于开始时间。';
  } else if (Number(filters.end) - Number(filters.start) > maxHours) {
    errors.time = `单次时段最多 ${maxHours} 小时，请缩短时段。`;
  }
  return errors;
}

export function filterInterval(filters: SearchFilters) {
  const midnight = Date.parse(`${filters.date}T00:00:00+08:00`);
  return { startsAt: new Date(midnight + Number(filters.start) * 3_600_000).toISOString(), endsAt: new Date(midnight + Number(filters.end) * 3_600_000).toISOString() };
}
