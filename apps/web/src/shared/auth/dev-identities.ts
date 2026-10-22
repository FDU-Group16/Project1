// TEMPORARY-DEPENDENCY WEB-D01-IDENTITY: explicit local development only. See docs/auth-integration.md.
import type { Identity } from './session';
export const devIdentityEnabled = import.meta.env.DEV && import.meta.env.VITE_USE_DEV_IDENTITY === 'true';
export const devIdentities: Array<{ token: string; user: Identity }> = [
  { token: 'dev-student-cs', user: { id: 'dev-student-cs', displayName: '开发学生 · 计算机', departmentId: 'cs', permissions: ['seat:reserve'] } },
  { token: 'dev-student-ee', user: { id: 'dev-student-ee', displayName: '开发学生 · 电子', departmentId: 'ee', permissions: ['seat:reserve'] } },
  { token: 'dev-room-admin', user: { id: 'dev-room-admin', displayName: '开发空间管理员', departmentId: null, permissions: ['room:manage'] } },
  { token: 'dev-operator', user: { id: 'dev-operator', displayName: '开发运维人员', departmentId: null, permissions: ['operations:read'] } },
];
