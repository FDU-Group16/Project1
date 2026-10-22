import type { RouteRecordRaw } from 'vue-router';

export const m1Routes: RouteRecordRaw[] = [
  { path: '/m1/settings', component: () => import('./pages/SettingsPage.vue'), meta: { title: '预约设置', section: 'm1', requiresAuth: true, permission: 'room:manage' } },
  {
    path: '/m1',
    name: 'm1-home',
    component: () => import('./pages/SeatSearchPage.vue'),
    meta: { title: '座位搜索', section: 'm1', requiresAuth: true },
  },
  {
    path: '/m1/preview',
    name: 'm1-preview',
    component: () => import('./pages/ModuleHome.vue'),
    props: { preview: true },
    meta: { title: '座位界面示例', section: 'm1', preview: true },
  },
  {
    path: '/m1/reservations',
    name: 'm1-reservations',
    component: () => import('./pages/LiveReservationsPage.vue'),
    meta: { title: '我的预约', section: 'm1', requiresAuth: true },
  },
  {
    path: '/m1/preview/reservations',
    name: 'm1-preview-reservations',
    component: () => import('./pages/ReservationsPage.vue'),
    props: { preview: true },
    meta: { title: '预约记录示例', section: 'm1', preview: true },
  },
  {
    path: '/m1/reservations/:id',
    name: 'm1-reservation-detail',
    component: () => import('./pages/LiveReservationDetailPage.vue'),
    meta: { title: '预约详情', section: 'm1', requiresAuth: true },
  },
  {
    path: '/m1/preview/reservations/:id',
    name: 'm1-preview-reservation-detail',
    component: () => import('./pages/ReservationDetailPage.vue'),
    props: { preview: true },
    meta: { title: '预约详情示例', section: 'm1', preview: true },
  },
];
