import type { RouteRecordRaw } from 'vue-router';

export const m2Routes: RouteRecordRaw[] = [
  {
    path: '/m2',
    name: 'm2-home',
    component: () => import('./pages/ModuleHome.vue'),
  },
  {
    path: '/m2/apply',
    name: 'm2-draft',
    component: () => import('./pages/DraftPage.vue'),
    meta: { title: '准备整室申请' },
  },
];
