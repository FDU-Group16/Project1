/**
 * Read-only UI examples for the explicit /m1/preview routes.
 * These are presentation models, not an API contract or a provider substitute.
 * No real room, person, availability or reservation is represented here.
 */
export interface ExampleSeat {
  label: string;
  socket: boolean;
  state: 'available' | 'occupied' | 'unavailable';
}

export interface ExampleRoom {
  key: string;
  name: string;
  scope: string;
  opens: number;
  closes: number;
  seats: ExampleSeat[];
}

function seats(prefix: string, count: number, sockets: boolean): ExampleSeat[] {
  return Array.from({ length: count }, (_, index) => ({
    label: `${prefix}-${String(index + 1).padStart(2, '0')}`,
    socket: sockets && index % 3 !== 2,
    state: index === count - 1 ? 'unavailable' : index === count - 2 ? 'occupied' : 'available',
  }));
}

export const exampleRooms: ExampleRoom[] = [
  { key: 'example-a201', name: '教学楼 A201', scope: '全校开放 · 示例', opens: 8, closes: 22, seats: seats('A', 14, true) },
  { key: 'example-b302', name: '院系自习室 B302', scope: '院系范围 · 示例', opens: 8, closes: 22, seats: seats('B', 6, true) },
  { key: 'example-c101', name: '阅览室 C101', scope: '全校开放 · 示例', opens: 9, closes: 22, seats: seats('C', 8, false) },
];

export interface ExampleReservation {
  key: string;
  room: string;
  seat: string;
  date: string;
  period: string;
  duration: string;
  status: string;
  socket: boolean;
  category: 'current' | 'history';
}

export const exampleReservations: ExampleReservation[] = [
  { key: 'example-current', room: '教学楼 A201', seat: 'A-08', date: '2026-10-23', period: '18:00–20:00', duration: '2 小时', status: '待开始', socket: true, category: 'current' },
  { key: 'example-history', room: '阅览室 C101', seat: 'C-02', date: '2026-10-20', period: '14:00–16:00', duration: '2 小时', status: '已结束', socket: false, category: 'history' },
];
