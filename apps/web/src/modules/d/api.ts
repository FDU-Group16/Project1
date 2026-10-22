import { request, jsonBody } from '../../shared/api/client';
export interface Room { id: string; name: string; departmentId: string | null; openHour: number; closeHour: number; weekdays: number[]; active: boolean; retired: boolean }
export interface Seat { id: string; roomId: string; number: string; hasSocket: boolean; active: boolean; retired: boolean }
export type RoomInput = Omit<Room, 'id' | 'retired'>;
export type SeatInput = Pick<Seat, 'number' | 'hasSocket' | 'active'>;
export const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
export const dApi = {
  rooms: () => request<{ items: Room[] }>('d', '/api/v1/rooms'),
  room: (id: string) => request<Room>('d', `/api/v1/rooms/${encodeURIComponent(id)}`),
  createRoom: (value: RoomInput) => request<Room>('d', '/api/v1/rooms', { method: 'POST', body: jsonBody(value) }),
  updateRoom: (id: string, value: Partial<RoomInput>) => request<Room>('d', `/api/v1/rooms/${encodeURIComponent(id)}`, { method: 'PATCH', body: jsonBody(value) }),
  retireRoom: (id: string) => request<Room>('d', `/api/v1/rooms/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  seats: (roomId: string) => request<{ items: Seat[] }>('d', `/api/v1/rooms/${encodeURIComponent(roomId)}/seats`),
  createSeat: (roomId: string, value: SeatInput) => request<Seat>('d', `/api/v1/rooms/${encodeURIComponent(roomId)}/seats`, { method: 'POST', body: jsonBody(value) }),
  updateSeat: (id: string, value: Partial<SeatInput>) => request<Seat>('d', `/api/v1/seats/${encodeURIComponent(id)}`, { method: 'PATCH', body: jsonBody(value) }),
  retireSeat: (id: string) => request<Seat>('d', `/api/v1/seats/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};
