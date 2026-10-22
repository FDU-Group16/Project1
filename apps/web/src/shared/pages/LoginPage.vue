<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';

const route = useRoute();
const router = useRouter();
const returnTo = computed(() => {
  const candidate = route.query.redirect;
  if (typeof candidate !== 'string' || !candidate.startsWith('/') || candidate.startsWith('//') || /[\\\u0000-\u0020]/.test(candidate)) return '/m1';
  const resolved = router.resolve(candidate);
  const isRegistered = resolved.matched.length > 0 && resolved.matched.every(record => !record.path.includes(':pathMatch'));
  return isRegistered && resolved.name !== 'login' && resolved.name !== 'not-found' ? resolved.fullPath : '/m1';
});
</script>

<template>
  <section class="login-page" aria-labelledby="login-title">
    <div class="login-context"><span class="ui-eyebrow">One campus. One place.</span><p>连接校园空间与每一天的学习生活。</p></div>
    <div class="login-panel ui-panel">
      <span class="login-emblem"><AppIcon name="shield" :size="30" /></span>
      <p class="login-kicker">统一身份入口</p>
      <h1 id="login-title">登录校园资源平台</h1>
      <p class="login-description">身份验证开放后，你可以查看可预约空间，<br class="wide-break">并管理自己的校园安排。</p>
      <div class="availability-note" role="status"><AppIcon name="clock" :size="18" /><div><strong>统一身份服务接入中</strong><p>目前暂不能登录，开放后可从此处进入。</p></div></div>
      <RouterLink to="/m1/preview" class="ui-button ui-button--primary preview-link">浏览界面示例<AppIcon name="arrow-right" :size="18" /></RouterLink>
      <p class="preview-note">只读合成样例 · 无需输入账号或密码</p>
      <div class="login-footer"><RouterLink :to="returnTo" class="ui-link"><AppIcon name="arrow-left" :size="16" />返回刚才的页面</RouterLink></div>
    </div>
    <p class="privacy-note"><AppIcon name="shield" :size="15" />此页不会采集登录信息或生成登录凭据。</p>
  </section>
</template>

<style scoped>
.login-page { width: 100%; max-width: 450px; margin: 0 auto; }
.login-context { text-align: center; margin-bottom: 28px; }
.login-context p { margin: 9px 0 0; color: var(--color-muted); font-size: 12px; }
.login-panel { padding: 38px 36px 24px; box-shadow: 0 8px 35px #193b2d04; }
.login-emblem { display: grid; place-items: center; width: 58px; height: 58px; background: var(--color-brand-soft); color: var(--color-brand); border-radius: 16px; margin-bottom: 25px; }
.login-kicker { font-size: 11px; color: var(--color-brand); margin-bottom: 9px; }
h1 { font-size: 25px; margin-bottom: 14px; }
.login-description { color: var(--color-muted); font-size: 12px; line-height: 1.9; margin-bottom: 26px; }
.availability-note { display: flex; gap: 10px; align-items: flex-start; padding: 15px; background: #f3f7f7; border: 1px solid #e3ebec; border-radius: 9px; margin-bottom: 24px; color: var(--color-muted); }
.availability-note .app-icon { margin-top: 2px; }
.availability-note strong { font-size: 12px; color: var(--color-text); font-weight: 550; }
.availability-note p { margin: 3px 0 0; font-size: 11px; }
.preview-link { width: 100%; }
.preview-note { text-align: center; font-size: 10px; margin: 12px 0 25px; color: var(--color-muted); }
.login-footer { display: flex; justify-content: center; border-top: 1px solid var(--color-border); padding-top: 18px; }
.login-footer .ui-link { font-size: 12px; min-height: 32px; }
.privacy-note { display: flex; justify-content: center; align-items: flex-start; gap: 6px; font-size: 10px; color: var(--color-muted); margin-top: 20px; }
@media (max-width: 480px) { .login-panel { padding: 28px 23px 20px; } h1 { font-size: 23px; } .wide-break { display: none; } }
</style>
