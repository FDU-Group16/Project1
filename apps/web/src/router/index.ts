import { createRouter, createWebHistory } from 'vue-router';
import { nextTick } from 'vue';
import { m1Routes } from '../modules/m1/routes';
import { m2Routes } from '../modules/m2/routes';
import { m3Routes } from '../modules/m3/routes';

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../shared/pages/HomePage.vue'),
      meta: { title: '首页' },
    },
    ...m1Routes,
    ...m2Routes.map(route => ({ ...route, meta: { ...route.meta, title: '整室申请' } })),
    ...m3Routes.map(route => ({ ...route, meta: { ...route.meta, title: '报修工单' } })),
    {
      path: '/login',
      name: 'login',
      component: () => import('../shared/pages/LoginPage.vue'),
      meta: { title: '统一登录' },
    },
    {
      path: '/403',
      name: 'forbidden',
      component: () => import('../shared/pages/ForbiddenPage.vue'),
      meta: { title: '暂无访问权限' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../shared/pages/NotFoundPage.vue'),
      meta: { title: '页面不存在' },
    },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition;
    return to.path === from.path ? false : { top: 0 };
  },
});

router.afterEach(async (to, from, failure) => {
  if (failure) return;
  document.title = `${typeof to.meta.title === 'string' ? to.meta.title : '校园服务'} · 校园资源服务平台`;
  if (from.matched.length && to.path !== from.path) {
    await nextTick();
    document.getElementById('main-content')?.focus({ preventScroll: true });
  }
});
