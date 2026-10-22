import { createRouter, createWebHistory } from 'vue-router';
import { m1Routes } from '../modules/m1/routes';
import { m2Routes } from '../modules/m2/routes';
import { m3Routes } from '../modules/m3/routes';

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../shared/components/ModuleIntro.vue'),
      props: {
        title: '校园资源服务平台',
        description: '工程骨架已就绪。业务功能将在需求和接口评审后逐步接入。',
      },
    },
    ...m1Routes,
    ...m2Routes,
    ...m3Routes,
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
});
