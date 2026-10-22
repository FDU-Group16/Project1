import { request, jsonBody } from '../../shared/api/client';
export interface Seat { id: string; roomId: string; roomName: string; number: string; hasSocket: boolean; departmentId?: string | null }
export interface Reservation { id: string; userId: string; roomId: string; roomName: string; seatId: string; seatNumber: string; startsAt: string; endsAt: string; status: 'RESERVED' | 'CHECKED_IN' | 'CANCELLED' | 'NO_SHOW' | 'COMPLETED'; createdAt: string; checkedInAt: string | null; dependencyMode?: string }
export interface Breach { id: string; reservationId: string; reason: string; occurredAt: string; roomId: string; seatId: string }
export interface Counts { reservations: number; checkedIn: number; cancelled: number; noShows: number; reservedHours: number }
export interface Operations { startsAt: string; endsAt: string; totals: Counts; rooms: Array<Counts & { roomId: string; roomName: string; seats: Array<Counts & { seatId: string; seatNumber: string }> }> }
export interface Provenance { id: string; sourceSystem: string; sourceId: string; roomId: string; action: string; createdAt: string; detail: unknown }
export const statusLabel: Record<Reservation['status'], string> = { RESERVED: '待签到', CHECKED_IN: '已签到', CANCELLED: '已取消', NO_SHOW: '已失约', COMPLETED: '已完成' };
export const formatTime = (value: string) => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
export const idempotencyKey = () => crypto.randomUUID();
export const m1Api = {
  seats: (startsAt: string, endsAt: string, hasSocket: boolean) => request<{ items: Seat[] }>('m1', `/api/v1/seats?${new URLSearchParams({ startsAt, endsAt, ...(hasSocket ? { hasSocket: 'true' } : {}) })}`),
  settings: () => request<{ maxReservationHours: number }>('m1', '/api/v1/settings'),
  updateSettings: (maxReservationHours: number) => request<{ maxReservationHours: number }>('m1', '/api/v1/settings', { method: 'PUT', body: jsonBody({ maxReservationHours }) }),
  reserve: (value: { seatId: string; roomId: string; startsAt: string; endsAt: string }, key: string) => request<Reservation>('m1', '/api/v1/reservations', { method: 'POST', headers: { 'Idempotency-Key': key }, body: jsonBody(value) }),
  reservations: (scope: string, offset = 0) => request<{ items: Reservation[]; total: number }>('m1', `/api/v1/reservations?${new URLSearchParams({ scope, offset: String(offset), limit: '10' })}`),
  reservation: (id: string) => request<Reservation>('m1', `/api/v1/reservations/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<Reservation>('m1', `/api/v1/reservations/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  checkIn: (id: string, code: string) => request<Reservation>('m1', `/api/v1/reservations/${encodeURIComponent(id)}/check-in`, { method: 'POST', body: jsonBody({ code }) }),
  rebook: (id: string, startsAt: string, endsAt: string, key: string) => request<Reservation>('m1', `/api/v1/reservations/${encodeURIComponent(id)}/rebook`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: jsonBody({ startsAt, endsAt }) }),
  breaches: (offset = 0) => request<{ items: Breach[]; total: number }>('m1', `/api/v1/breaches?offset=${offset}&limit=10`),
  operations: (startsAt: string, endsAt: string) => request<Operations>('m1', `/api/v1/operations?${new URLSearchParams({ startsAt, endsAt })}`),
  code: (roomId: string) => request<{ roomId: string; date: string; code: string; expiresAt: string }>('m1', `/api/v1/rooms/${encodeURIComponent(roomId)}/check-in-code`),
  provenance: (roomId: string, offset = 0) => request<{ items: Provenance[]; total: number }>('m1', `/api/v1/rooms/${encodeURIComponent(roomId)}/provenance?offset=${offset}&limit=10`),
};
