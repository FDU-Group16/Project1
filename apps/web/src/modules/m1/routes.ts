import type { RouteRecordRaw } from 'vue-router';

export const m1Routes: RouteRecordRaw[] = [
  {
    path: '/m1',
    name: 'm1-home',
    component: () => import('./pages/ModuleHome.vue'),
  },
];
