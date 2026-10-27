import { request, ApiError } from '../../shared/api/client';

export type Role = 'reporter' | 'admin' | 'technician';
export interface Identity { id: string; name: string; role: Role }
export interface M3Context {
  mode: string;
  directoryMode: string;
  m1Mode: string;
  businessReady: boolean;
}
export interface Room { id: string; name: string }
export type Category = 'facilities' | 'electrical' | 'environment' | 'other';
export type OrderStatus = 'SUBMITTED' | 'ASSIGNED' | 'BLOCK_PENDING' | 'IN_PROGRESS' | 'PENDING_ACCEPTANCE' | 'RELEASE_PENDING' | 'CLOSED' | 'CANCELLED';
export type OrderAction = 'assign' | 'start' | 'complete' | 'accept' | 'reject' | 'cancel' | 'rate' | 'retry-sync';
export interface HistoryItem { id: string; action: string; actorId: string; actorName: string; note: string; createdAt: string }
export interface WorkOrder {
  id: string; roomId: string; roomName: string; category: Category; title: string; description: string;
  reporterId: string; reporterName: string; assigneeId: string | null; assigneeName: string | null;
  status: OrderStatus; version: number; createdAt: string; updatedAt: string; dueAt: string | null; escalated: boolean;
  rating: { score: number; comment: string; createdAt: string } | null;
  sync: { status: 'pending' | 'processing' | 'succeeded' | 'failed'; attempts: number; error: string | null; retryable: boolean } | null;
  history: HistoryItem[]; allowedActions: OrderAction[];
}
export interface NewOrder { roomId: string; category: Category; title: string; description: string }
export interface ActionInput { version: number; assigneeId?: string; note?: string; score?: number; comment?: string }

const base = '/v1';
export async function fetchContext(signal?: AbortSignal): Promise<M3Context> {
  const response = await request<M3Context>('m3', `${base}/context`, { signal });
  // Retain dependency modes only; legacy standalone demo identity payloads are not a session.
  return { mode: response.mode, directoryMode: response.directoryMode, m1Mode: response.m1Mode, businessReady: response.businessReady };
}

// CONTRACT-ASSUMPTION WEB-M3-D01: shared auth supplies the bearer and owns expiry/logout.
export function createM3Api(sessionSignal?: AbortSignal) {
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const signal = sessionSignal && init.signal ? AbortSignal.any([sessionSignal, init.signal]) : sessionSignal ?? init.signal;
    const result = await request<T>('m3', `${base}${path}`, { ...init, signal });
    // A successful old response must never trigger navigation after an identity switch.
    signal?.throwIfAborted();
    return result;
  }
  return {
    me: (signal?: AbortSignal) => call<Identity>('/me', { signal }),
    rooms: (signal?: AbortSignal) => call<{ items: Room[] }>('/rooms', { signal }),
    technicians: (signal?: AbortSignal) => call<{ items: Identity[] }>('/technicians', { signal }),
    orders: (signal?: AbortSignal) => call<{ items: WorkOrder[] }>('/work-orders', { signal }),
    order: (id: string, signal?: AbortSignal) => call<WorkOrder>(`/work-orders/${encodeURIComponent(id)}`, { signal }),
    create: (body: NewOrder, key: string, signal?: AbortSignal) => call<WorkOrder>('/work-orders', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify(body), signal,
    }),
    action: (id: string, action: OrderAction, body: ActionInput, signal?: AbortSignal) => call<WorkOrder>(`/work-orders/${encodeURIComponent(id)}/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
    }),
  };
}
export type M3Api = ReturnType<typeof createM3Api>;
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return '登录已失效，请通过统一登录重新进入。';
    if (error.status === 403) return '当前身份没有此操作的权限。';
    if (error.status === 404) return '工单不存在，或当前身份无权查看。';
    if (error.status === 409) return '工单已更新或请求发生冲突，请核对最新内容后重试。';
    if (error.status === 503) return '依赖服务尚未就绪，请稍后重试。';
    return error.message || '请求未能完成，请检查填写内容。';
  }
  return '连接服务失败，请检查网络后重试。';
}
