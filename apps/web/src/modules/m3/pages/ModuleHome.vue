<script setup lang="ts">
import { computed, onMounted, onUnmounted, provide, ref } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { describeError, isAbort } from '../api';
import { devIdentities } from '../devIdentities';
import { roleLabels } from '../labels';
import { createM3Session, M3_SESSION } from '../session';

const session = createM3Session();
provide(M3_SESSION, session);
const { context, actor, loading, error, token, generation } = session;
const contextLoading = ref(true);
const contextError = ref('');
const route = useRoute();
const actorRoles = computed(() => actor.value?.roles.map(role => roleLabels[role]).join(' / ') ?? '');
let alive = true;
async function loadContext() {
  contextLoading.value = true;
  contextError.value = '';
  try { const data = await session.api.context(); if (alive) context.value = data; }
  catch (cause) { if (alive && !isAbort(cause)) contextError.value = describeError(cause); }
  finally { if (alive) contextLoading.value = false; }
}
onMounted(loadContext);
onUnmounted(() => { alive = false; session.reset(); });
</script>

<template>
  <div class="m3-module">
    <header class="m3-heading">
      <div><p class="ui-eyebrow">CAMPUS MAINTENANCE</p><h1>让校园设施，回到好状态</h1><p class="m3-subtitle">上报、维修、验收，每一步都有记录。</p></div>
      <div class="m3-heading-icon" aria-hidden="true"><AppIcon name="wrench" :size="31" /></div>
    </header>
    <div v-if="contextLoading" class="m3-service-state ui-panel" role="status">正在连接报修服务…</div>
    <section v-else-if="contextError" class="m3-service-state ui-panel" role="alert">
      <AppIcon name="info" :size="28" /><h2>暂时无法连接报修服务</h2><p>{{ contextError }}</p><button class="ui-button" @click="loadContext">重新连接</button>
    </section>
    <template v-else-if="context">
      <section v-if="context.mode === 'development'" class="m3-dev-notice" aria-label="开发环境说明">
        <div class="m3-dev-copy"><span class="m3-dev-label">开发联调</span><p>当前身份与房间为合成数据。<strong v-if="context.dependencyMode === 'stub'">座位联动使用模拟依赖，不代表 M1 已接入。</strong><span v-else-if="context.dependencyMode === 'http'">座位联动调用已配置的 HTTP 服务，真实集成仍需验收。</span><span v-else>座位服务尚未配置，维修与验收将无法完成联动。</span></p></div>
        <div class="m3-identity"><label for="m3-identity">开发身份</label><select id="m3-identity" :value="token" @change="session.selectIdentity(($event.target as HTMLSelectElement).value)"><option value="">请选择联调身份</option><option v-for="identity in devIdentities" :key="identity.token" :value="identity.token">{{ identity.label }}</option></select></div>
      </section>
      <section v-else class="m3-service-state ui-panel">
        <AppIcon name="shield" :size="30" /><h2>统一身份服务尚未接入</h2><p>正式报修需要验证身份和房间访问权限。接入完成后，即可在这里创建和跟进工单。</p><p v-if="context.message" class="m3-context-message">{{ context.message }}</p><RouterLink to="/login" class="ui-button">查看统一登录入口</RouterLink>
      </section>
      <p v-if="error" class="m3-error" role="alert">{{ error }}</p>
      <div v-if="loading" class="m3-service-state ui-panel" role="status">正在验证身份和加载房间目录…</div>
      <template v-else-if="actor">
        <nav class="m3-nav" aria-label="报修模块导航">
          <div class="m3-tabs"><RouterLink to="/m3" :class="{ active: route.name === 'm3-home' || route.name === 'm3-detail' }">工单中心</RouterLink><RouterLink v-if="actor.roles.includes('student')" to="/m3/new" :class="{ active: route.name === 'm3-new' }">上报故障</RouterLink></div>
          <span class="m3-current-actor"><AppIcon name="user" :size="15" />{{ actor.name }}<span class="m3-role">{{ actorRoles }}</span></span>
        </nav>
        <RouterView v-slot="{ Component }"><component :is="Component" :key="`${route.fullPath}:${generation}`" /></RouterView>
      </template>
      <section v-else-if="context.mode === 'development' && !loading && !error" class="m3-service-state ui-panel">
        <AppIcon name="user" :size="28" /><h2>选择一个联调身份</h2><p>报修人上报与验收，物业调度派单，维修人员处理工单。切换身份会清空当前页面数据。</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.m3-module { max-width: 1050px; margin: 0 auto; }
.m3-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 26px; }
.m3-heading h1 { margin: 9px 0 10px; font-size: clamp(25px, 3vw, 32px); }
.m3-heading .ui-eyebrow { margin-bottom: 0; }
.m3-subtitle { color: var(--color-muted); font-size: 14px; margin: 0; }
.m3-heading-icon { display: grid; place-items: center; width: 68px; height: 68px; color: var(--color-brand); background: var(--color-brand-soft); border-radius: 20px; flex: none; }
.m3-dev-notice { display: flex; align-items: center; gap: 28px; border: 1px solid #e9dcc0; background: #fffcf4; padding: 17px 20px; border-radius: 11px; margin-bottom: 25px; }
.m3-dev-copy { flex: 1; min-width: 0; }
.m3-dev-label { font-size: 11px; font-weight: 650; letter-spacing: .08em; color: #87602b; }
.m3-dev-copy p { margin: 5px 0 0; color: #776a51; font-size: 12px; line-height: 1.8; }
.m3-dev-copy strong { font-weight: 550; }
.m3-identity { min-width: 225px; display: grid; gap: 5px; }
.m3-identity label { font-size: 12px; color: #6f624a; }
.m3-identity select { max-width: 100%; min-width: 0; width: 100%; min-height: 42px; padding: 8px 11px; border: 1px solid #dfd4bd; background: #fff; border-radius: 7px; font-size: 13px; }
.m3-nav { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 24px; border-bottom: 1px solid var(--color-border); }
.m3-tabs { display: flex; gap: 26px; }
.m3-tabs a { padding: 0 0 15px; text-decoration: none; color: var(--color-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; font-size: 14px; }
.m3-tabs a.active { color: var(--color-brand); border-color: var(--color-brand); font-weight: 600; }
.m3-current-actor { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 6px; color: var(--color-muted); font-size: 12px; padding-bottom: 15px; }
.m3-role { border-left: 1px solid var(--color-border); padding-left: 7px; margin-left: 2px; }
.m3-service-state { display: grid; justify-items: center; text-align: center; gap: 13px; padding: 48px 25px; color: var(--color-muted); margin-top: 20px; }
.m3-service-state > svg { color: var(--color-brand); }
.m3-service-state h2 { font-size: 19px; margin: 0; }
.m3-service-state p { font-size: 14px; max-width: 530px; margin: 0; line-height: 1.8; }
.m3-service-state .m3-context-message { font-size: 12px; }
.m3-service-state .ui-button { margin-top: 5px; }
.m3-error { color: var(--color-danger); background: #fff2f1; border: 1px solid #f0d5d3; padding: 14px 18px; border-radius: 9px; font-size: 13px; }
@media (max-width: 680px) { .m3-heading-icon { display: none; } .m3-dev-notice { align-items: stretch; flex-direction: column; gap: 13px; padding: 16px; } .m3-identity { min-width: 0; } .m3-identity select { font-size: 16px; } .m3-nav { align-items: flex-start; flex-direction: column-reverse; gap: 5px; } .m3-current-actor { padding-bottom: 8px; } .m3-service-state { padding: 35px 18px; } }
</style>
