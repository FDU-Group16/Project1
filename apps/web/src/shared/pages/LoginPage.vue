<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { auth, login, devIdentityEnabled, devIdentities, selectDevIdentity, logout } from '../auth';
import { errorMessage } from '../api/client';
const route = useRoute(); const router = useRouter();
const account = ref(''); const password = ref(''); const busy = ref(false); const error = ref('');
const selectedIdentity = ref(devIdentities[0]?.token ?? '');
const returnTo = computed(() => {
  const candidate = route.query.redirect;
  if (typeof candidate !== 'string' || !candidate.startsWith('/') || candidate.startsWith('//') || /[\\\u0000-\u0020]/.test(candidate)) return '/m1';
  const resolved = router.resolve(candidate);
  return resolved.matched.length && resolved.matched.every(record => !record.path.includes(':pathMatch')) && resolved.name !== 'login' ? resolved.fullPath : '/m1';
});
async function submit() {
  busy.value = true; error.value = '';
  try { await login(account.value, password.value); password.value = ''; await router.replace(returnTo.value); }
  catch (cause) { error.value = errorMessage(cause); password.value = ''; }
  finally { busy.value = false; }
}
async function enterDevelopment() { selectDevIdentity(selectedIdentity.value); await router.replace(returnTo.value); }
async function exit() { try { await logout(); } catch { error.value = '本机登录状态已清除；服务端退出请求未成功，请在身份服务恢复后确认。'; } }
</script>
<template>
  <section class="login-page" aria-labelledby="login-title">
    <div class="login-panel ui-panel"><span class="login-emblem"><AppIcon name="shield" :size="30" /></span><p class="ui-eyebrow">CAMPUS IDENTITY</p><h1 id="login-title">登录校园资源平台</h1>
      <p class="feature-note">通过统一身份服务验证账号。身份服务未部署时会明确报告失败，不会创建模拟登录。</p>
      <p v-if="auth.notice" class="feature-error" role="status">{{ auth.notice }}</p><p v-if="error" class="feature-error" role="alert">{{ error }}</p>
      <div v-if="auth.session" class="feature-panel"><p>当前身份：{{ auth.session.user.displayName }}</p><p v-if="auth.session.synthetic" class="feature-error">当前使用合成开发身份。</p><button type="button" class="ui-button" @click="exit">退出登录</button></div>
      <form v-else-if="!devIdentityEnabled" @submit.prevent="submit"><label class="feature-field">账号<input v-model="account" name="username" autocomplete="username" required maxlength="100" /></label><label class="feature-field">密码<input v-model="password" name="password" autocomplete="current-password" type="password" required maxlength="200" /></label><button class="ui-button ui-button--primary login-submit" :disabled="busy">{{ busy ? '正在验证…' : '登录' }}</button></form>
      <form v-if="devIdentityEnabled" class="dev-panel" @submit.prevent="enterDevelopment"><strong>开发模式 · 合成身份</strong><p>这里不验证密码。仅用于本机联调，后端也必须明确启用开发身份模式。所有业务操作仍调用真实后端。</p><label class="feature-field">选择开发身份<select v-model="selectedIdentity"><option v-for="item in devIdentities" :key="item.token" :value="item.token">{{ item.user.displayName }}</option></select></label><button class="ui-button ui-button--primary login-submit">{{ auth.session ? '切换开发身份' : '使用开发身份' }}</button></form>
      <div class="login-footer"><RouterLink :to="returnTo" class="ui-link">返回刚才的页面</RouterLink><RouterLink to="/m1/preview" class="ui-link">浏览只读示例</RouterLink></div>
    </div>
  </section>
</template>
<style scoped src="../styles/feature.css"></style>
<style scoped>.login-page{max-width:450px;margin:0 auto}.login-panel{padding:32px}.login-emblem{display:grid;place-items:center;width:58px;height:58px;background:var(--color-brand-soft);color:var(--color-brand);border-radius:16px;margin-bottom:24px}.feature-field{margin:18px 0}.login-submit{width:100%;margin-top:10px}.login-footer{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-top:1px solid var(--color-border);padding-top:20px;margin-top:24px;font-size:12px}.dev-panel{border:2px solid #bb7822;border-radius:9px;padding:18px;background:#fff8e9}.dev-panel>strong{color:#82520f}.dev-panel>p{font-size:12px;line-height:1.8}@media(max-width:480px){.login-panel{padding:22px}}</style>
