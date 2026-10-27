import { reactive } from 'vue';

// CONTRACT-ASSUMPTION WEB-D01-IDENTITY：Web M1/D-02 消费的身份/会话字段来自 D-01（M2 组）契约提案，可在协作范围内对齐调整。
// 保留会话过期、身份切换和退出清理；完整修改/替换边界见 docs/auth-integration.md。
export interface Identity { id: string; displayName: string; departmentId: string | null; permissions: string[] }
// TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：synthetic 是本地开发标记，不是 D-01 响应要求；替身清理时可协调移除该字段及使用分支。
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
