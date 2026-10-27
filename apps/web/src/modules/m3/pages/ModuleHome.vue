<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { errorMessage, type OrderStatus, type WorkOrder } from '../api';
import { categoryLabels, formatTime, shortId, statusLabels } from '../presentation';
import { useM3Session } from '../session';

const { identity, api } = useM3Session();
const route = useRoute();
const router = useRouter();
const orders = ref<WorkOrder[]>([]);
const loading = ref(true);
const error = ref('');
const search = ref('');
const status = ref<OrderStatus | ''>('');
const room = ref('');
const view = computed(() => typeof route.query.view === 'string' ? route.query.view : 'all');
let controller: AbortController | null = null;
let sequence = 0;
let timer: ReturnType<typeof setInterval> | undefined;
const tabs = computed(() => [
  { key: 'all', label: '全部工单' }, { key: 'mine', label: '我的报修' },
  ...(identity.role === 'technician' ? [{ key: 'assigned', label: '分配给我' }] : []),
  { key: 'acceptance', label: '待我验收' }, { key: 'overdue', label: '超时待办' },
]);
const rooms = computed(() => Array.from(new Map(orders.value.map(order => [order.roomId, order.roomName])).entries()));
const pending = computed(() => orders.value.filter(order => !['CLOSED', 'CANCELLED'].includes(order.status)).length);
const acceptance = computed(() => orders.value.filter(order => order.allowedActions.includes('accept')).length);
const overdue = computed(() => orders.value.filter(order => order.escalated && !['CLOSED', 'CANCELLED'].includes(order.status)).length);
const visible = computed(() => orders.value.filter(order => {
  if (view.value === 'mine' && order.reporterId !== identity.id) return false;
  if (view.value === 'assigned' && order.assigneeId !== identity.id) return false;
  if (view.value === 'active' && ['CLOSED', 'CANCELLED'].includes(order.status)) return false;
  if (view.value === 'acceptance' && !order.allowedActions.includes('accept')) return false;
  if (view.value === 'overdue' && !(order.escalated && !['CLOSED', 'CANCELLED'].includes(order.status))) return false;
  if (status.value && order.status !== status.value) return false;
  if (room.value && order.roomId !== room.value) return false;
  const query = search.value.trim().toLowerCase();
  return !query || `${order.title} ${order.id} ${order.roomName}`.toLowerCase().includes(query);
}));
async function load(silent = false) {
  controller?.abort();
  const abort = new AbortController();
  controller = abort;
  const current = ++sequence;
  if (!silent) loading.value = true;
  try {
    const result = await api.orders(abort.signal);
    if (current !== sequence || abort.signal.aborted) return;
    orders.value = result.items;
    error.value = '';
  } catch (caught) {
    if (current === sequence && !abort.signal.aborted) error.value = errorMessage(caught);
  } finally { if (current === sequence) loading.value = false; }
}
function setView(next: string) { void router.replace({ path: '/m3', query: next === 'all' ? {} : { view: next } }); }
function clearFilters() { search.value = ''; status.value = ''; room.value = ''; setView('all'); }
onMounted(() => { void load(); timer = setInterval(() => { if (!document.hidden) void load(true); }, 15000); });
onBeforeUnmount(() => { sequence += 1; controller?.abort(); clearInterval(timer); });
</script>

<template>
  <section aria-labelledby="m3-title">
    <header class="page-heading"><div><p class="m3-eyebrow">REPAIR & CARE</p><h1 id="m3-title">让每个问题，都有回应。</h1><p class="page-description">从故障上报到验收完成，在这里跟进每一步。</p></div><RouterLink to="/m3/new" class="ui-button ui-button--primary"><span class="plus" aria-hidden="true">+</span>发起报修</RouterLink></header>
    <div class="summary-grid" aria-label="当前可见工单概览">
      <button class="summary-card" @click="clearFilters"><span><AppIcon name="grid" :size="17" />可见工单</span><strong>{{ loading && !orders.length ? '—' : orders.length }}</strong><small>当前身份有权访问</small></button>
      <button class="summary-card" @click="status = ''; setView('active')"><span><AppIcon name="wrench" :size="17" />处理中</span><strong>{{ loading && !orders.length ? '—' : pending }}</strong><small>从待派单到等待恢复</small></button>
      <button class="summary-card accent-card" @click="setView('acceptance')"><span><AppIcon name="check" :size="17" />待我验收</span><strong>{{ loading && !orders.length ? '—' : acceptance }}</strong><small>维修完工，等待确认</small></button>
      <button class="summary-card" :class="{ 'warning-card': overdue > 0 }" @click="setView('overdue')"><span><AppIcon name="clock" :size="17" />超时升级</span><strong>{{ loading && !orders.length ? '—' : overdue }}</strong><small>已进入管理员跟进范围</small></button>
    </div>
    <div v-if="error" class="m3-alert" role="alert">{{ error }}<button class="ui-button" :disabled="loading" @click="load()">重新加载</button></div>
    <div class="work-orders ui-panel">
      <div class="list-topline"><h2>工单记录<span>{{ visible.length }}</span></h2><button class="refresh-button" :disabled="loading" @click="load()"><AppIcon name="clock" :size="14" />{{ loading ? '更新中' : '刷新' }}</button></div>
      <nav class="view-tabs" aria-label="工单视图"><button v-for="tab in tabs" :key="tab.key" :class="{ active: view === tab.key }" :aria-current="view === tab.key ? 'page' : undefined" @click="setView(tab.key)">{{ tab.label }}</button></nav>
      <p v-if="view === 'active'" class="active-filter">正在查看处理中的工单 <button @click="setView('all')">显示全部</button></p>
      <div class="filters"><label class="search-filter"><span class="ui-sr-only">搜索标题、工单号或房间</span><AppIcon name="search" :size="17" /><input v-model="search" type="search" placeholder="搜索标题、工单号或房间"></label><label><span class="ui-sr-only">工单状态</span><select v-model="status"><option value="">全部状态</option><option v-for="(label, key) in statusLabels" :key="key" :value="key">{{ label }}</option></select></label><label><span class="ui-sr-only">报修房间</span><select v-model="room"><option value="">全部房间</option><option v-for="[id, name] in rooms" :key="id" :value="id">{{ name }}</option></select></label></div>
      <div v-if="loading && !orders.length" class="m3-empty" role="status"><AppIcon name="clock" :size="29" /><h2>正在加载工单</h2><p>稍等片刻，正在读取最新进度。</p></div>
      <div v-else-if="!visible.length" class="m3-empty"><AppIcon name="leaf" :size="32" /><h2>{{ orders.length ? '没有符合条件的工单' : '这里还没有工单' }}</h2><p>{{ orders.length ? '调整筛选条件，看看其他记录。' : '发现空间或设施问题，可以从一次报修开始。' }}</p><button v-if="orders.length" class="ui-button" @click="clearFilters">清除筛选</button><RouterLink v-else to="/m3/new" class="ui-button">发起第一条报修</RouterLink></div>
      <div v-else class="order-list">
        <RouterLink v-for="order in visible" :key="order.id" :to="`/m3/work-orders/${encodeURIComponent(order.id)}`" class="order-row">
          <div class="order-icon"><AppIcon :name="order.category === 'electrical' ? 'plug' : order.category === 'environment' ? 'leaf' : 'wrench'" :size="21" /></div>
          <div class="order-main"><div class="order-title"><h3>{{ order.title }}</h3><span v-if="order.escalated && !['CLOSED','CANCELLED'].includes(order.status)" class="escalated-label">已升级</span></div><p><span>{{ order.roomName }}</span><span class="meta-divider">·</span><span>{{ categoryLabels[order.category] }}</span><span class="meta-divider">·</span><span>#{{ shortId(order.id) }}</span></p><p class="mobile-owner">{{ order.assigneeName ? `维修：${order.assigneeName}` : '等待安排维修人员' }}</p></div>
          <div class="order-person"><span>{{ order.assigneeName || '待分配' }}</span><small>{{ formatTime(order.createdAt) }}</small></div>
          <div class="order-status"><StatusBadge :status="order.status" /><small v-if="order.sync?.status === 'failed'" class="sync-error">同步待处理</small><small v-else-if="order.dueAt">时限 {{ formatTime(order.dueAt) }}</small></div><AppIcon name="chevron-right" :size="16" class="row-arrow" />
        </RouterLink>
      </div>
      <div class="list-footer"><span>工单进度每 15 秒自动更新</span><span>时间按当前设备时区显示</span></div>
    </div>
    <div class="service-note"><AppIcon name="shield" :size="18" /><p>维修期间，相关房间保持下架。验收通过后，仅解除本工单的限制；其他预约或维修安排仍然有效。</p></div>
  </section>
</template>

<style scoped>
.page-heading { display:flex; justify-content:space-between; align-items:center; gap:24px; margin-bottom:28px; }
h1 { font-size:clamp(24px,2.8vw,32px); margin-bottom:10px; }
.page-description { font-size:13px; color:var(--color-muted); margin:0; }
.page-heading > .ui-button { flex-shrink:0; }
.plus { font-size:22px; line-height:1; font-weight:400; }
.summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:15px; margin-bottom:28px; }
.summary-card { text-align:left; border:1px solid var(--color-border); border-radius:12px; padding:19px 20px; background:var(--color-surface); color:var(--color-text); }
.summary-card > span { display:flex; gap:7px; align-items:center; color:var(--color-muted); font-size:12px; }
.summary-card strong { display:block; font-size:31px; font-weight:600; margin:10px 0 2px; line-height:1.3; font-variant-numeric:tabular-nums; }
.summary-card small { font-size:10px; color:var(--color-muted); }
.summary-card:hover { border-color:#aecdd0; }
.accent-card { background:#edf6f5; border-color:#d5e9e5; }
.accent-card > span,.accent-card strong { color:#216b66; }
.warning-card strong { color:#a07027; }
.work-orders { overflow:hidden; }
.list-topline { display:flex; justify-content:space-between; align-items:center; padding:23px 24px 0; }
.list-topline h2 { font-size:16px; margin:0; display:flex; align-items:center; gap:10px; }
.list-topline h2 span { font-size:10px; color:var(--color-muted); padding:2px 7px; border-radius:5px; background:#edf2f3; }
.refresh-button { display:flex; gap:5px; align-items:center; font-size:11px; background:none; border:0; color:var(--color-muted); min-height:40px; }
.view-tabs { display:flex; gap:25px; padding:9px 24px 0; border-bottom:1px solid var(--color-border); overflow-x:auto; }
.view-tabs button { flex-shrink:0; background:none; border:0; border-bottom:2px solid transparent; padding:13px 0; min-height:45px; color:var(--color-muted); font-size:12px; }
.view-tabs button.active { color:var(--color-brand); border-bottom-color:var(--color-brand); font-weight:650; }
.active-filter { margin:12px 24px 0; font-size:12px; color:var(--color-muted); }
.active-filter button { background:none; border:0; color:var(--color-brand); text-decoration:underline; }
.filters { display:grid; grid-template-columns:minmax(0,1fr) 145px 175px; gap:10px; padding:18px 24px; background:#fcfdfd; border-bottom:1px solid #e8eeee; }
.filters label { min-width:0; }
.filters input,.filters select { width:100%; min-width:0; border:1px solid #dce5e6; background:#fff; border-radius:7px; min-height:40px; padding:8px 11px; font-size:12px; }
.search-filter { position:relative; }
.search-filter .app-icon { position:absolute; top:12px; left:11px; color:#84969b; }
.search-filter input { padding-left:35px; }
.order-row { display:flex; gap:15px; align-items:center; padding:23px 24px; text-decoration:none; color:inherit; border-bottom:1px solid #edf1f2; }
.order-row:last-child { border-bottom:0; }
.order-row:hover { background:#f7fbfb; }
.order-icon { display:grid; place-items:center; background:#f0f5f5; color:#67929a; width:43px; height:43px; border-radius:10px; flex-shrink:0; }
.order-main { min-width:0; flex:1; }
.order-title { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.order-main h3 { margin:0; font-size:14px; font-weight:600; overflow-wrap:anywhere; }
.order-main p { display:flex; flex-wrap:wrap; gap:6px; font-size:11px; color:var(--color-muted); margin:7px 0 0; }
.meta-divider { color:#c0cdcf; }
.escalated-label { font-size:9px; color:#966620; background:#fcf3df; padding:1px 5px; border-radius:3px; }
.order-person { display:grid; gap:6px; min-width:90px; font-size:12px; }
.order-person small,.order-status small { font-size:10px; color:var(--color-muted); }
.order-status { display:grid; justify-items:start; gap:6px; min-width:130px; }
.order-status .sync-error { color:var(--color-danger); }
.row-arrow { color:#9aabad; }
.order-main .mobile-owner { display:none; }
.list-footer { display:flex; justify-content:space-between; gap:10px; padding:13px 24px; background:#fcfdfd; color:#839397; font-size:10px; border-top:1px solid #edf1f2; }
.service-note { display:flex; gap:10px; align-items:flex-start; margin:22px 4px 0; color:#7b9195; }
.service-note p { font-size:11px; line-height:1.8; margin:0; }
@media(max-width:900px) { .summary-card { padding:16px 14px; } .summary-grid { gap:10px; } .order-person { display:none; } .order-main .mobile-owner { display:flex; } .filters { grid-template-columns:minmax(0,1fr) 120px 145px; } }
@media(max-width:650px) { .page-heading { flex-wrap:wrap; gap:18px; } .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .summary-card { padding:16px; } .summary-card strong { font-size:28px; } .filters { grid-template-columns:repeat(2,minmax(0,1fr)); padding:14px 16px; } .search-filter { grid-column:1/-1; } .filters input,.filters select { font-size:16px; } .list-topline { padding:17px 16px 0; } .view-tabs { padding-inline:16px; gap:20px; } .order-row { padding:19px 16px; gap:10px; flex-wrap:wrap; } .order-icon { width:35px; height:35px; border-radius:8px; align-self:flex-start; } .order-main { flex-basis:calc(100% - 55px); } .order-status { margin-left:45px; display:flex; align-items:center; flex-wrap:wrap; min-width:0; } .row-arrow { margin-left:auto; } .list-footer { padding-inline:16px; flex-wrap:wrap; } }
</style>
