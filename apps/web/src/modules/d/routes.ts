import type { RouteRecordRaw } from 'vue-router';
export const dRoutes: RouteRecordRaw[] = [
  { path: '/d/rooms', name: 'd-rooms', component: () => import('./pages/RoomsPage.vue'), meta: { title: '房间与座位管理', section: 'd', requiresAuth: true, permission: 'room:manage' } },
  { path: '/d/rooms/new', name: 'd-room-new', component: () => import('./pages/RoomEditorPage.vue'), meta: { title: '登记房间', section: 'd', requiresAuth: true, permission: 'room:manage' } },
  { path: '/d/rooms/:roomId', name: 'd-room', component: () => import('./pages/RoomEditorPage.vue'), meta: { title: '房间详情与座位', section: 'd', requiresAuth: true, permission: 'room:manage' } },
];
