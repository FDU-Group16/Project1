import type { RouteRecordRaw } from 'vue-router';
export const m3Routes: RouteRecordRaw[] = [{
  path: '/m3',
  component: () => import('./pages/ModuleHome.vue'),
  children: [
    { path: '', name: 'm3-home', component: () => import('./pages/WorkOrdersPage.vue'), meta: { title: '报修工单' } },
    { path: 'new', name: 'm3-new', component: () => import('./pages/NewOrderPage.vue'), meta: { title: '上报故障' } },
    { path: 'orders/:id', name: 'm3-detail', component: () => import('./pages/OrderDetailPage.vue'), meta: { title: '工单详情' } },
  ],
}];
