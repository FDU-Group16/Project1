import type { RouteRecordRaw } from 'vue-router';

export const m3Routes: RouteRecordRaw[] = [
  {
    path: '/m3',
    name: 'm3-home',
    component: () => import('./pages/ModuleHome.vue'),
  },
];
