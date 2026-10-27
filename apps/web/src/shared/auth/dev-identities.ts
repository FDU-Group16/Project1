// TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：Web M1/D-02 消费 D-01（M2 组）的合成身份替身，仅显式开发模式启用。
// M2 提供方与 Web/M1/D-02 消费方可在集成任务范围内修改或替换此文件；真实联调通过后按清单移除。
// 保留真实身份客户端、会话清理与业务代码；精确范围见 docs/auth-integration.md。
import type { Identity } from './session';
export const devIdentityEnabled = import.meta.env.DEV && import.meta.env.VITE_USE_DEV_IDENTITY === 'true';
export const devIdentities: Array<{ token: string; user: Identity }> = [
  { token: 'dev-student-cs', user: { id: 'dev-student-cs', displayName: '开发学生 · 计算机', departmentId: 'cs', permissions: ['seat:reserve'] } },
  { token: 'dev-student-ee', user: { id: 'dev-student-ee', displayName: '开发学生 · 电子', departmentId: 'ee', permissions: ['seat:reserve'] } },
  { token: 'dev-room-admin', user: { id: 'dev-room-admin', displayName: '开发空间管理员', departmentId: null, permissions: ['room:manage'] } },
  { token: 'dev-operator', user: { id: 'dev-operator', displayName: '开发运维人员', departmentId: null, permissions: ['operations:read'] } },
];
