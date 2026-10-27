import { inject, ref, type InjectionKey } from 'vue';
import { createM3Api, describeError, isAbort } from './api';
import type { Actor, DirectoryItem, PendingCreate, ServiceContext } from './types';

export function createM3Session() {
  const context = ref<ServiceContext | null>(null);
  const actor = ref<Actor | null>(null);
  const rooms = ref<DirectoryItem[]>([]);
  const technicians = ref<DirectoryItem[]>([]);
  const token = ref('');
  const generation = ref(0);
  const pendingCreate = ref<PendingCreate | null>(null);
  const loading = ref(false);
  const error = ref('');
  const api = createM3Api(() => token.value);
  function reset() {
    api.abortAll();
    generation.value += 1;
    actor.value = null;
    rooms.value = [];
    technicians.value = [];
    pendingCreate.value = null;
    token.value = '';
    error.value = '';
  }
  async function selectIdentity(selected: string) {
    reset();
    if (context.value?.mode !== 'development' || !selected) { loading.value = false; return; }
    token.value = selected;
    loading.value = true;
    const current = generation.value;
    try {
      const profile = await api.me();
      if (current !== generation.value) return;
      const [roomData, technicianData] = await Promise.all([
        api.rooms(), profile.roles.includes('dispatcher') ? api.technicians() : Promise.resolve({ items: [] }),
      ]);
      if (current !== generation.value) return;
      actor.value = profile;
      rooms.value = roomData.items;
      technicians.value = technicianData.items;
    } catch (cause) {
      if (current === generation.value && !isAbort(cause)) { error.value = describeError(cause); token.value = ''; }
    } finally { if (current === generation.value) loading.value = false; }
  }
  return { context, actor, rooms, technicians, token, generation, pendingCreate, loading, error, api, reset, selectIdentity };
}
export type M3Session = ReturnType<typeof createM3Session>;
export const M3_SESSION: InjectionKey<M3Session> = Symbol('m3-session');
export function useM3Session(): M3Session {
  const session = inject(M3_SESSION);
  if (!session) throw new Error('M3 page must be rendered within the M3 module layout');
  return session;
}
