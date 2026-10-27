import { auth, clearSession } from '../auth/session';
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return '无法连接服务，请检查网络后重试。';
}
export async function request<T>(service: 'm1' | 'd' | 'm3', path: string, options: RequestInit = {}): Promise<T> {
  const epoch = auth.epoch;
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (auth.session) headers.set('Authorization', `Bearer ${auth.session.accessToken}`);
  const controller = new AbortController();
  const cancel = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) cancel();
  else options.signal?.addEventListener('abort', cancel, { once: true });
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(`/api/${service}${path}`, { ...options, headers, signal: controller.signal });
    if (epoch !== auth.epoch) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
    const body = response.status === 204 ? undefined : await response.json().catch(error => {
      if (controller.signal.aborted) throw error;
      if (response.ok) throw new ApiError(response.status, 'INVALID_RESPONSE', '服务返回了无法识别的数据，请稍后重试。');
      return undefined;
    });
    if (epoch !== auth.epoch) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
    if (!response.ok) {
      // Anonymous password failures must stay on the form instead of remounting it via auth.epoch.
      if (response.status === 401 && auth.session) clearSession('登录已过期或无效，请重新登录。');
      throw new ApiError(response.status, body?.error?.code ?? body?.code ?? 'HTTP_ERROR', body?.error?.message ?? body?.detail ?? (response.status === 403 ? '当前身份没有此操作权限。' : `服务暂时不可用（${response.status}），请稍后重试。`));
    }
    return body as T;
  }
  catch (error) {
    if (epoch !== auth.epoch && !(error instanceof ApiError && error.status === 401)) throw new ApiError(0, 'SESSION_CHANGED', '身份已变更，请重新打开页面。');
    throw error;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', cancel);
  }
}
export const jsonBody = (value: unknown) => JSON.stringify(value);
