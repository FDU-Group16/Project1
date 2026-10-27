<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { describeError, isAbort } from '../api';
import { categoryLabels, displayTime, statusLabels } from '../labels';
import { useM3Session } from '../session';
import type { WorkOrder } from '../types';

const session = useM3Session();
const { actor } = session;
const orders = ref<WorkOrder[]>([]);
const loading = ref(true);
const error = ref('');
const query = ref('');
const filter = ref('all');
let alive = true;
let requestVersion = 0;
const activeOrders = computed(() => orders.value.filter(order => !['CLOSED', 'CANCELLED'].includes(order.status)));
const waitingAcceptance = computed(() => orders.value.filter(order => order.status === 'PENDING_ACCEPTANCE'));
const visibleOrders = computed(() => orders.value.filter(order => {
  const matchesFilter = filter.value === 'all' || (filter.value === 'open' && !['CLOSED', 'CANCELLED'].includes(order.status)) || order.status === filter.value;
  const text = query.value.trim().toLowerCase();
  return matchesFilter && (!text || `${order.title} ${order.roomName} ${order.id}`.toLowerCase().includes(text));
}));
const scopeDescription = computed(() => actor.value?.roles.includes('dispatcher') ? '查看全部工单，安排维修并跟进超时事项。' : actor.value?.roles.includes('technician') ? '这里展示分配给你的工单，记录维修过程与完工情况。' : '这里展示你上报的工单，随时查看进度并完成验收。');
async function refresh() {
  const current = ++requestVersion;
  loading.value = true;
  error.value = '';
  try { const data = await session.api.list(); if (alive && current === requestVersion) orders.value = data.items; }
  catch (cause) { if (alive && current === requestVersion && !isAbort(cause)) error.value = describeError(cause); }
  finally { if (alive && current === requestVersion) loading.value = false; }
}
onMounted(refresh);
onUnmounted(() => { alive = false; });
</script>

<template>
  <section aria-labelledby="m3-list-title">
    <div class="m3-page-heading"><div><h2 id="m3-list-title">工单中心</h2><p>{{ scopeDescription }}</p></div><RouterLink v-if="actor?.roles.includes('student')" to="/m3/new" class="ui-button ui-button--primary"><span aria-hidden="true" class="m3-plus">＋</span>上报故障</RouterLink></div>
    <div class="m3-metrics" aria-label="当前可见工单统计">
      <div><span>处理中</span><strong>{{ loading && !orders.length ? '—' : activeOrders.length }}</strong><p>持续跟进，直到验收</p></div>
      <div><span>待验收</span><strong>{{ loading && !orders.length ? '—' : waitingAcceptance.length }}</strong><p>完工后由报修人确认</p></div>
      <div><span>已完成</span><strong>{{ loading && !orders.length ? '—' : orders.filter(order => order.status === 'CLOSED').length }}</strong><p>已验收并确认联动结果</p></div>
    </div>
    <div class="m3-list-panel ui-panel" :aria-busy="loading">
      <div class="m3-toolbar">
        <div class="m3-search"><AppIcon name="search" :size="17" /><label class="ui-sr-only" for="m3-query">搜索工单标题、房间或编号</label><input id="m3-query" v-model="query" type="search" placeholder="搜索标题、房间或工单编号" /></div>
        <div class="m3-filter"><label class="ui-sr-only" for="m3-filter">筛选工单状态</label><select id="m3-filter" v-model="filter"><option value="all">全部状态</option><option value="open">处理中</option><option v-for="(label, status) in statusLabels" :key="status" :value="status">{{ label }}</option></select><button class="ui-button m3-refresh" :disabled="loading" @click="refresh">{{ loading ? '刷新中…' : '刷新' }}</button></div>
      </div>
      <div v-if="error" class="m3-list-message m3-error" role="alert"><AppIcon name="info" :size="24" /><p>{{ error }}</p><button class="ui-button" @click="refresh">重新加载</button></div>
      <div v-else-if="loading && !orders.length" class="m3-list-message" role="status"><AppIcon name="clock" :size="26" /><p>正在加载工单…</p></div>
      <div v-else-if="!orders.length" class="m3-list-message"><span class="m3-empty-icon"><AppIcon name="wrench" :size="28" /></span><h3>{{ actor?.roles.includes('technician') ? '暂时没有分配给你的工单' : '暂无工单' }}</h3><p>{{ actor?.roles.includes('student') ? '设施出现故障时，记录位置和问题，我们一起跟进处理。' : '新的工单会在这里展示，请稍后刷新查看。' }}</p><RouterLink v-if="actor?.roles.includes('student')" to="/m3/new" class="ui-button">上报第一张工单</RouterLink></div>
      <div v-else-if="!visibleOrders.length" class="m3-list-message"><AppIcon name="search" :size="26" /><h3>没有符合条件的工单</h3><p>试着调整关键词或状态筛选。</p><button class="ui-button" @click="query = ''; filter = 'all'">清除筛选</button></div>
      <ul v-else class="m3-orders">
        <li v-for="order in visibleOrders" :key="order.id">
          <RouterLink :to="{ name: 'm3-detail', params: { id: order.id } }" class="m3-order-link">
            <span class="m3-category-icon" aria-hidden="true"><AppIcon :name="order.category === 'electrical' ? 'plug' : 'wrench'" :size="23" /></span>
            <div class="m3-order-content"><div class="m3-order-title"><h3>{{ order.title }}</h3><StatusBadge :status="order.status" /><span v-if="order.escalated" class="m3-alert-badge">已升级</span></div><p class="m3-order-location"><AppIcon name="location" :size="13" />{{ order.roomName || order.roomId }}<span aria-hidden="true">·</span>{{ categoryLabels[order.category] }}</p><p class="m3-order-meta"><span>上报于 {{ displayTime(order.createdAt) }}</span><span class="m3-id">{{ order.id }}</span></p><p v-if="order.syncStatus === 'FAILED'" class="m3-sync-error">座位联动未完成，需要处理同步问题。</p></div>
            <AppIcon class="m3-row-arrow" name="chevron-right" :size="18" />
          </RouterLink>
        </li>
      </ul>
      <div v-if="!error && orders.length" class="m3-list-footer" role="status">显示 {{ visibleOrders.length }} 张工单 · {{ loading ? '正在更新' : '仅展示当前身份可见的数据' }}</div>
    </div>
    <p class="m3-note"><AppIcon name="info" :size="14" />维修提交完工后，房间仍保持下架，直到验收与恢复同步完成。时间均为北京时间。</p>
  </section>
</template>

<style scoped>
.m3-page-heading { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 22px; }
.m3-page-heading h2 { margin: 0 0 7px; font-size: 21px; }
.m3-page-heading p { margin: 0; font-size: 13px; color: var(--color-muted); }
.m3-page-heading > a { flex: none; }
.m3-plus { font-size: 20px; line-height: 1; font-weight: 400; }
.m3-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 24px; }
.m3-metrics > div { padding: 18px 22px; border: 1px solid var(--color-border); border-radius: 12px; background: #fff; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px; }
.m3-metrics span { font-size: 13px; color: var(--color-muted); }
.m3-metrics strong { font-weight: 550; font-size: 29px; color: var(--color-brand); line-height: 1.2; }
.m3-metrics p { grid-column: 1 / -1; margin: 0; font-size: 11px; color: var(--color-muted); }
.m3-list-panel { overflow: hidden; }
.m3-toolbar { display: flex; gap: 14px; padding: 18px 22px; border-bottom: 1px solid var(--color-border); }
.m3-search { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; color: var(--color-muted); border: 1px solid var(--color-border); border-radius: 8px; padding: 0 12px; }
.m3-search input { border: 0; width: 100%; min-width: 0; background: transparent; padding: 10px 0; font-size: 13px; }
.m3-search:focus-within { outline: 2px solid var(--color-brand); outline-offset: 2px; }
.m3-search input:focus { outline: 0; }
.m3-filter { display: flex; gap: 10px; }
.m3-filter select { font-size: 13px; border: 1px solid var(--color-border); border-radius: 8px; padding: 9px 11px; background: #fff; max-width: 100%; }
.m3-refresh { min-width: 65px; font-size: 13px; }
.m3-orders { padding: 0; margin: 0; list-style: none; }
.m3-orders li + li { border-top: 1px solid #edf1f2; }
.m3-order-link { display: flex; align-items: center; gap: 18px; padding: 23px 22px; text-decoration: none; color: inherit; transition: background .15s; }
.m3-order-link:hover { background: #f9fbfb; }
.m3-order-link:focus-visible { outline-offset: -4px; }
.m3-category-icon { width: 47px; height: 47px; background: #f0f6f6; color: #6b8c91; border-radius: 11px; display: grid; place-items: center; flex: none; }
.m3-order-content { min-width: 0; flex: 1; }
.m3-order-title { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.m3-order-title h3 { margin: 0; font-size: 15px; overflow-wrap: anywhere; }
.m3-order-location { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin: 7px 0; font-size: 12px; color: var(--color-muted); }
.m3-order-meta { display: flex; flex-wrap: wrap; gap: 5px 16px; font-size: 11px; color: #829095; margin: 0; }
.m3-id { overflow-wrap: anywhere; }
.m3-row-arrow { color: #9aa9ac; }
.m3-alert-badge { color: #a24830; font-size: 11px; border: 1px solid #efd2c6; padding: 2px 6px; border-radius: 4px; }
.m3-sync-error { font-size: 12px; color: var(--color-danger); margin: 8px 0 0; }
.m3-list-message { display: grid; justify-items: center; gap: 12px; padding: 50px 25px; color: var(--color-muted); text-align: center; }
.m3-list-message h3 { font-size: 17px; margin: 0; }
.m3-list-message p { font-size: 13px; margin: 0; }
.m3-list-message .ui-button { margin-top: 6px; }
.m3-empty-icon { display: grid; place-items: center; width: 62px; height: 62px; background: #eff6f6; color: var(--color-brand); border-radius: 50%; margin-bottom: 6px; }
.m3-list-message.m3-error { color: var(--color-danger); }
.m3-list-footer { background: #fcfdfd; border-top: 1px solid var(--color-border); padding: 12px 22px; font-size: 11px; color: var(--color-muted); }
.m3-note { display: flex; gap: 7px; color: var(--color-muted); font-size: 12px; line-height: 1.8; margin: 16px 0 0; }
.m3-note svg { margin-top: 3px; }
@media (max-width: 720px) { .m3-metrics { gap: 10px; } .m3-metrics > div { padding: 16px; grid-template-columns: 1fr; gap: 8px; } .m3-metrics p { display: none; } .m3-toolbar { flex-direction: column; padding: 16px; } .m3-filter select { flex: 1; min-width: 0; } .m3-search input, .m3-filter select { font-size: 16px; } .m3-order-link { padding: 20px 16px; gap: 12px; } .m3-category-icon { display: none; } }
@media (max-width: 430px) { .m3-page-heading { align-items: stretch; flex-direction: column; gap: 15px; } .m3-page-heading > a { align-self: flex-start; } .m3-metrics > div { padding: 13px; } .m3-metrics strong { font-size: 25px; } .m3-order-title { gap: 8px; } .m3-order-title h3 { flex-basis: 100%; } }
</style>
