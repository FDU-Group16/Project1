<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, provide, ref, shallowRef, watch } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { auth } from '../../../shared/auth';
import { createM3Api, errorMessage, fetchContext, type M3Context } from '../api';
import { m3SessionKey, type M3Session } from '../session';
import { roleLabels } from '../presentation';

const route = useRoute();
const router = useRouter();
const context = shallowRef<M3Context | null>(null);
const session = shallowRef<M3Session | null>(null);
const busy = ref(true);
const error = ref('');
let operation = 0;
let controller: AbortController | null = null;
const isDevelopment = computed(() => Boolean(auth.session?.synthetic) || context.value?.mode === 'development');
const loginTarget = computed(() => ({ path: '/login', query: { redirect: route.fullPath } }));
const dependencyDescription = computed(() => {
  const identity = auth.session?.synthetic ? '使用公共登录提供的合成开发身份。' : '身份通过统一登录验证。';
  const rooms = context.value?.directoryMode === 'development' ? '房间使用本地合成目录。' : '房间由主数据服务查询。';
  const seats = context.value?.m1Mode === 'development-http' ? '座位同步使用开发替身，不代表真实座位已下架或恢复。' : '座位同步以 M1 实际回执为准。';
  return identity + rooms + seats;
});
provide(m3SessionKey, () => {
  if (!session.value) throw new Error('M3 session is unavailable');
  return session.value;
});
function invalidate() {
  operation += 1;
  controller?.abort();
  session.value = null;
  context.value = null;
}
async function bootstrap() {
  invalidate();
  if (!auth.session) { await router.replace(loginTarget.value); return; }
  const activeOperation = operation;
  const activeEpoch = auth.epoch;
  const abort = new AbortController();
  controller = abort;
  busy.value = true;
  error.value = '';
  try {
    const response = await fetchContext(abort.signal);
    if (abort.signal.aborted || activeOperation !== operation || activeEpoch !== auth.epoch) return;
    context.value = response;
    if (!response.businessReady) { busy.value = false; return; }
    const api = createM3Api(abort.signal);
    const identity = await api.me(abort.signal);
    if (abort.signal.aborted || activeOperation !== operation || activeEpoch !== auth.epoch) return;
    session.value = { identity, api, context: response };
  } catch (caught) {
    if (!abort.signal.aborted && activeOperation === operation && activeEpoch === auth.epoch) error.value = errorMessage(caught);
  } finally {
    if (activeOperation === operation) busy.value = false;
  }
}
// Shared App.vue remounts the route on auth.epoch; cancel immediately before that render.
watch(() => auth.epoch, invalidate, { flush: 'sync' });
onMounted(bootstrap);
onBeforeUnmount(invalidate);
</script>

<template>
  <div class="m3-module">
    <div class="module-topline">
      <RouterLink to="/m3" class="module-brand"><span class="module-emblem"><AppIcon name="wrench" :size="19" /></span><span>校园报修<span class="module-caption">CARE FOR OUR CAMPUS</span></span></RouterLink>
      <nav aria-label="报修模块导航" class="module-nav"><RouterLink to="/m3" :aria-current="route.name === 'm3-home' ? 'page' : undefined">工单工作台</RouterLink><RouterLink v-if="session" to="/m3/new" :aria-current="route.name === 'm3-new' ? 'page' : undefined">发起报修</RouterLink></nav>
    </div>
    <div v-if="isDevelopment && context" class="demo-banner" role="status">
      <div class="demo-message"><AppIcon name="info" :size="18" /><div><strong>开发联调模式</strong><span>{{ dependencyDescription }}</span></div></div>
      <RouterLink :to="loginTarget" class="identity-settings">管理登录身份<AppIcon name="arrow-right" :size="14" /></RouterLink>
    </div>
    <div v-if="busy" class="m3-state ui-panel" role="status"><span class="loading-dot"></span><h1>正在进入报修工作台</h1><p>正在确认当前身份与可用服务。</p></div>
    <div v-else-if="error" class="m3-state ui-panel" role="alert"><AppIcon name="info" :size="32" /><h1>暂时无法进入</h1><p>{{ error }}</p><button class="ui-button ui-button--primary" @click="bootstrap">重新连接</button><RouterLink :to="loginTarget" class="ui-button">前往统一登录</RouterLink></div>
    <div v-else-if="!context?.businessReady" class="m3-state ui-panel"><AppIcon name="shield" :size="34" /><h1>报修服务准备中</h1><p>身份或房间服务尚未接入，暂时无法提交工单。服务准备好后，你可以在这里跟进报修全流程。</p><button class="ui-button" @click="bootstrap">重新检查</button></div>
    <template v-else-if="session">
      <div class="identity-line"><span class="identity-dot"></span>{{ session.identity.name }}<span class="role-chip">{{ roleLabels[session.identity.role] }}</span><span class="identity-note">仅展示当前身份有权访问的工单</span></div>
      <RouterView v-slot="{ Component }"><component :is="Component" :key="`${auth.epoch}:${route.path}`" /></RouterView>
    </template>
  </div>
</template>

<style scoped>
.m3-module { min-width:0; }
.module-topline { display:flex; justify-content:space-between; align-items:center; gap:20px; padding-bottom:22px; border-bottom:1px solid var(--color-border); margin-bottom:22px; }
.module-brand { display:flex; align-items:center; gap:10px; color:var(--color-text); text-decoration:none; font-size:15px; font-weight:650; }
.module-emblem { width:36px; height:36px; display:grid; place-items:center; border:1px solid #cfe1e4; border-radius:10px; background:#e9f3f4; color:var(--color-brand); }
.module-caption { display:block; font-size:8px; letter-spacing:.14em; font-weight:500; color:var(--color-muted); }
.module-nav { display:flex; gap:18px; }
.module-nav a { min-height:44px; display:flex; align-items:center; color:var(--color-muted); font-size:13px; text-decoration:none; }
.module-nav a[aria-current] { color:var(--color-brand); font-weight:650; }
.demo-banner { display:flex; justify-content:space-between; gap:20px; align-items:center; border:1px solid #e6d9bb; background:#fffbf1; border-radius:10px; padding:14px 16px; margin-bottom:20px; }
.demo-message { display:flex; align-items:flex-start; gap:10px; color:#805d25; }
.demo-message > .app-icon { margin-top:3px; }
.demo-message strong { display:block; font-size:12px; }
.demo-message span { display:block; font-size:11px; color:#7c6a46; margin-top:2px; max-width:440px; }
.identity-settings { display:inline-flex; align-items:center; gap:6px; min-height:40px; color:#805d25; font-size:11px; text-decoration:none; flex-shrink:0; }
.identity-line { display:flex; align-items:center; flex-wrap:wrap; gap:7px; font-size:12px; color:var(--color-muted); margin:0 0 25px; }
.identity-dot { width:6px; height:6px; background:#4e9185; border-radius:50%; }
.role-chip { padding:1px 6px; border-radius:4px; background:#eaf0f1; font-size:10px; }
.identity-note { margin-left:auto; color:#7b8b8f; font-size:11px; }
.loading-dot { display:inline-block; width:18px; height:18px; border:2px solid #d9e6e7; border-top-color:var(--color-brand); border-radius:50%; }
.m3-state { text-align:center; padding:60px 25px; color:var(--color-muted); }
.m3-state h1 { font-size:22px; margin:16px 0 12px; }
.m3-state p { max-width:500px; margin:0 auto 24px; font-size:14px; }
.m3-state .ui-button + .ui-button { margin-left:10px; }
.m3-module :deep(.m3-field) { display:grid; gap:7px; font-size:13px; font-weight:550; }
.m3-module :deep(.m3-field input),.m3-module :deep(.m3-field select),.m3-module :deep(.m3-field textarea),.m3-module :deep(.m3-control) { width:100%; min-width:0; min-height:44px; border:1px solid #cedbdd; border-radius:8px; padding:10px 12px; background:var(--color-surface); font-size:14px; font-weight:400; }
.m3-module :deep(.m3-field textarea) { resize:vertical; min-height:130px; }
.m3-module :deep(.m3-field small) { font-weight:400; color:var(--color-muted); font-size:11px; }
.m3-module :deep(.m3-alert) { display:flex; flex-wrap:wrap; align-items:center; gap:10px; border:1px solid #e6c5c7; background:#fff5f5; color:var(--color-danger); padding:13px 16px; border-radius:8px; font-size:13px; margin-bottom:18px; }
.m3-module :deep(.m3-empty) { text-align:center; padding:46px 24px; color:var(--color-muted); }
.m3-module :deep(.m3-empty h2) { margin:14px 0 10px; font-size:18px; }
.m3-module :deep(.m3-empty p) { font-size:13px; }
.m3-module :deep(.m3-eyebrow) { margin-bottom:8px; color:var(--color-brand); font-size:10px; letter-spacing:.15em; font-weight:650; }
@media(max-width:650px) { .module-topline { gap:12px; flex-wrap:wrap; padding-bottom:16px; } .module-nav { gap:15px; } .demo-banner { flex-direction:column; align-items:stretch; gap:12px; } .identity-note { margin-left:0; flex-basis:100%; margin-top:2px; } }
@media(max-width:380px) { .module-brand { font-size:14px; } .module-nav { width:100%; gap:25px; } .module-nav a { min-height:32px; } }
</style>
