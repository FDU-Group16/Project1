import { auth, clearSession } from '../auth/session';
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return '无法连接服务，请检查网络后重试。';
}
export async function request<T>(service: 'm1' | 'd', path: string, options: RequestInit = {}): Promise<T> {
  const epoch = auth.epoch;
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (auth.session) headers.set('Authorization', `Bearer ${auth.session.accessToken}`);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  let response: Response;
  try { response = await fetch(`/api/${service}${path}`, { ...options, headers, signal: controller.signal }); }
  catch (error) {
    if (epoch !== auth.epoch) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
    throw error;
  } finally { clearTimeout(timeout); }
  if (epoch !== auth.epoch) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
  const body = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (epoch !== auth.epoch) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
  if (!response.ok) {
    if (response.status === 401) clearSession('登录已过期或无效，请重新登录。');
    throw new ApiError(response.status, body?.code ?? 'HTTP_ERROR', body?.detail ?? (response.status === 403 ? '当前身份没有此操作权限。' : `服务暂时不可用（${response.status}），请稍后重试。`));
  }
  return body as T;
}
export const jsonBody = (value: unknown) => JSON.stringify(value);
