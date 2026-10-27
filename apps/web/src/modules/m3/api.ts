import type { Actor, DirectoryItem, NewOrder, OrderAction, ServiceContext, WorkOrder } from './types';

const API_BASE = '/api/m3/v1';
export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly code = '') { super(message); }
}

function errorMessage(status: number, data: unknown): string {
  if (status === 401) return '当前身份已失效，请重新选择开发身份；正式登录仍待接入。';
  if (status === 403) return '当前身份没有执行此操作的权限。';
  if (status === 404) return '未找到这张工单，或当前身份无权查看。';
  if (status === 409) return '工单状态或提交内容已变化，请刷新后核对，再重新操作。';
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) return '填写内容不符合要求，请检查字段长度、必填项和选项。';
  }
  return status === 503 ? '所需服务暂不可用，请稍后重试。' : `请求未能完成（${status}），请稍后重试。`;
}

/** Module-local adapter. It sends only M3 requests; M1 writeback belongs to the backend. */
export function createM3Api(getToken: () => string) {
  const active = new Set<AbortController>();
  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    active.add(controller);
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 20000);
    try {
      const headers = new Headers(options.headers);
      headers.set('Accept', 'application/json');
      if (options.body) headers.set('Content-Type', 'application/json');
      const token = getToken();
      if (token) headers.set('Authorization', `Bearer ${token}`);
      const response = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal, cache: 'no-store' });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const code = typeof data === 'object' && data !== null && 'code' in data && typeof data.code === 'string' ? data.code : '';
        throw new ApiError(response.status, errorMessage(response.status, data), code);
      }
      if (!data || typeof data !== 'object') throw new ApiError(0, '服务返回了无法识别的数据，请确认 M3 服务及转发配置。');
      return data as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted && !timedOut) throw error;
      throw new ApiError(0, timedOut ? '请求超时，结果尚未确认。请刷新核对，或使用相同内容重试上报。' : '无法连接报修服务。请检查网络或稍后重试。');
    } finally {
      window.clearTimeout(timeout);
      active.delete(controller);
    }
  }
  return {
    abortAll: () => { for (const controller of active) controller.abort(); active.clear(); },
    context: () => request<ServiceContext>('/context'),
    me: () => request<Actor>('/me'),
    rooms: () => request<{ items: DirectoryItem[] }>('/rooms'),
    technicians: () => request<{ items: DirectoryItem[] }>('/technicians'),
    list: () => request<{ items: WorkOrder[] }>('/work-orders'),
    get: (id: string) => request<WorkOrder>(`/work-orders/${encodeURIComponent(id)}`),
    create: (payload: NewOrder, key: string) => request<WorkOrder>('/work-orders', {
      method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(payload),
    }),
    act: (id: string, action: OrderAction, payload: Record<string, unknown>) => request<WorkOrder>(`/work-orders/${encodeURIComponent(id)}/${action}`, {
      method: 'POST', body: JSON.stringify(payload),
    }),
  };
}
export const isAbort = (error: unknown): boolean => error instanceof DOMException && error.name === 'AbortError';
export const describeError = (error: unknown): string => error instanceof Error ? error.message : '请求未完成，请稍后重试。';
