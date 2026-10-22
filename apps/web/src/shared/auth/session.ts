import { reactive } from 'vue';

export interface Identity { id: string; displayName: string; departmentId: string | null; permissions: string[] }
export interface Session { accessToken: string; expiresAt: string; user: Identity; synthetic?: boolean }
const key = 'campus.session.v1';
export const auth = reactive({ session: null as Session | null, epoch: 0, restored: false, notice: '' });
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
export const hasPermission = (permission: string) => Boolean(auth.session?.user.permissions.includes(permission));
export function clearSession(notice = '') {
  clearTimeout(expiryTimer);
  auth.session = null;
  auth.epoch += 1;
  auth.notice = notice;
  sessionStorage.removeItem(key);
}
export function setSession(session: Session) {
  clearSession();
  auth.session = session;
  sessionStorage.setItem(key, JSON.stringify(session));
  const remaining = Date.parse(session.expiresAt) - Date.now();
  expiryTimer = setTimeout(() => clearSession('登录已过期，请重新登录。'), Math.max(0, Math.min(remaining, 2_147_483_647)));
}
export function storedSession(): Session | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) ?? 'null') as Session | null;
    if (!value?.accessToken || !value.user?.id || !Array.isArray(value.user.permissions) || !Number.isFinite(Date.parse(value.expiresAt)) || Date.parse(value.expiresAt) <= Date.now()) return null;
    return value;
  } catch { return null; }
}
