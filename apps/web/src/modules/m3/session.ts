import { inject, type InjectionKey } from 'vue';
import type { Identity, M3Api, M3Context } from './api';

// Shell recreates this object and every child page on each identity change.
export interface M3Session { identity: Identity; api: M3Api; context: M3Context }
export const m3SessionKey: InjectionKey<() => M3Session> = Symbol('m3-session');
export function useM3Session(): M3Session {
  const resolve = inject(m3SessionKey);
  if (!resolve) throw new Error('M3 page requires its module shell');
  return resolve();
}
