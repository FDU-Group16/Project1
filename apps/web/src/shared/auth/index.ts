import { request, jsonBody } from '../api/client';
import { auth, clearSession, setSession, storedSession, type Identity, type Session } from './session';
import { devIdentities, devIdentityEnabled } from './dev-identities';
export { auth, hasPermission } from './session';
export { devIdentities, devIdentityEnabled } from './dev-identities';
let restorePromise: Promise<void> | undefined;
export function restoreIdentity() {
  if (auth.restored) return Promise.resolve();
  if (restorePromise) return restorePromise;
  restorePromise = (async () => {
    const session = storedSession();
    if (session?.synthetic) {
      const identity = devIdentityEnabled && devIdentities.find(item => item.token === session.accessToken);
      if (identity) setSession({ ...session, user: identity.user });
      else clearSession();
    } else if (session) {
      setSession(session);
      try { const user = await request<Identity>('d', '/api/v1/auth/me'); setSession({ ...session, user }); }
      catch { clearSession('身份服务暂时不可用，无法恢复登录。请重试。'); }
    }
    auth.restored = true;
  })();
  return restorePromise;
}
export async function login(account: string, password: string) {
  const result = await request<Session>('d', '/api/v1/auth/login', { method: 'POST', body: jsonBody({ username: account, password }) });
  if (!result.accessToken || !result.user?.id || !Array.isArray(result.user.permissions) || Date.parse(result.expiresAt) <= Date.now() || !Number.isFinite(Date.parse(result.expiresAt))) throw new Error('Invalid session response');
  setSession(result);
}
export function selectDevIdentity(token: string) {
  const identity = devIdentityEnabled && devIdentities.find(item => item.token === token);
  if (!identity) return;
  setSession({ accessToken: identity.token, user: identity.user, expiresAt: new Date(Date.now() + 3_600_000).toISOString(), synthetic: true });
}
export async function logout() {
  const synthetic = auth.session?.synthetic;
  try { if (!synthetic && auth.session) await request('d', '/api/v1/auth/logout', { method: 'POST' }); }
  finally { clearSession(); }
}
