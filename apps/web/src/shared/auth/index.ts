import { request, jsonBody } from '../api/client';
import { auth, clearSession, setSession, storedSession, type Identity, type Session } from './session';
import { devIdentities, devIdentityEnabled } from './dev-identities';
// CONTRACT-ASSUMPTION WEB-D01-IDENTITY：Web M1/D-02 消费 D-01（M2 组），真实 login/me/logout 接口采用 contracts/d-dependencies.md 提案。
// 提供方与消费方可在协作范围内对齐路径、字段和会话语义；保留真实 HTTP 客户端、失败处理与会话清理，不能整块删除。
// 临时分支与替换检查见 docs/auth-integration.md；接口提案不代表 D-01 已实现或批准。
export { auth, hasPermission } from './session';
export { devIdentities, devIdentityEnabled } from './dev-identities';
let restorePromise: Promise<void> | undefined;
export function restoreIdentity() {
  if (auth.restored) return Promise.resolve();
  if (restorePromise) return restorePromise;
  restorePromise = (async () => {
    const session = storedSession();
    // TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：仅此合成身份恢复分支可随 M2/D-01 联调替换；保留后续真实 /me 恢复与失败清理。
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
// TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：Web M1/D-02 的开发身份选择入口，可由提供/消费组在集成范围内修改或移除。
export function selectDevIdentity(token: string) {
  const identity = devIdentityEnabled && devIdentities.find(item => item.token === token);
  if (!identity) return;
  setSession({ accessToken: identity.token, user: identity.user, expiresAt: new Date(Date.now() + 3_600_000).toISOString(), synthetic: true });
}
export async function logout() {
  // TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：synthetic 只让开发替身跳过真实退出；替换时保留 /logout 请求及 finally 清理。
  const synthetic = auth.session?.synthetic;
  try { if (!synthetic && auth.session) await request('d', '/api/v1/auth/logout', { method: 'POST' }); }
  finally { clearSession(); }
}
