import type { RouteRecordRaw } from 'vue-router';

export const m2Routes: RouteRecordRaw[] = [
  {
    path: '/m2',
    name: 'm2-home',
    component: () => import('./pages/ModuleHome.vue'),
  },
];
