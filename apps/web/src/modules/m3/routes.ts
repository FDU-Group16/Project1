import type { RouteRecordRaw } from 'vue-router';

export const m3Routes: RouteRecordRaw[] = [
  {
    path: '/m3',
    meta: { section: 'm3', requiresAuth: true },
    component: () => import('./pages/M3Shell.vue'),
    children: [
      { path: '', name: 'm3-home', component: () => import('./pages/ModuleHome.vue') },
      { path: 'new', name: 'm3-new', component: () => import('./pages/NewOrder.vue') },
      { path: 'work-orders/:id', name: 'm3-detail', component: () => import('./pages/WorkOrderDetail.vue') },
    ],
  },
];
