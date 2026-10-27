<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { ApiError, describeError, isAbort } from '../api';
import { actionLabels, categoryLabels, displayTime } from '../labels';
import { useM3Session } from '../session';
import type { OrderAction, WorkOrder } from '../types';

const session = useM3Session();
const { actor, technicians, context } = session;
const route = useRoute();
const id = String(route.params.id ?? '');
const order = ref<WorkOrder | null>(null);
const loading = ref(true);
const fetchError = ref('');
const actionError = ref('');
const actionMessage = ref('');
const busy = ref(false);
const needsRefresh = ref(false);
const assigneeId = ref('');
const resolution = ref('');
const rejectReason = ref('');
const cancelReason = ref('');
const retryReason = ref('');
const rating = ref('');
const comment = ref('');
let alive = true;
let readSequence = 0;
let refreshInFlight = false;
let pollTimer: ReturnType<typeof setInterval> | undefined;
const isReporter = computed(() => !!order.value && actor.value?.id === order.value.reporterId);
const isAssignedTechnician = computed(() => actor.value?.roles.includes('technician') && actor.value.id === order.value?.assigneeId);
const isDispatcher = computed(() => actor.value?.roles.includes('dispatcher'));
const cancellable = computed(() => isReporter.value && ['REPORTED', 'ASSIGNED'].includes(order.value?.status ?? ''));
const assignable = computed(() => isDispatcher.value && ['REPORTED', 'ASSIGNED'].includes(order.value?.status ?? ''));
const pendingSync = computed(() => ['STARTING_REPAIR', 'ACCEPTING'].includes(order.value?.status ?? ''));
const finished = computed(() => ['CLOSED', 'CANCELLED'].includes(order.value?.status ?? ''));
const stepIndex = computed(() => {
  const status = order.value?.status;
  if (status === 'CLOSED') return 4;
  if (status === 'PENDING_ACCEPTANCE' || status === 'ACCEPTING') return 3;
  if (status === 'IN_PROGRESS') return 2;
  if (status === 'ASSIGNED' || status === 'STARTING_REPAIR') return 1;
  return 0;
});
const hasActions = computed(() => assignable.value || cancellable.value ||
  (isAssignedTechnician.value && ['ASSIGNED', 'IN_PROGRESS'].includes(order.value?.status ?? '')) ||
  (isReporter.value && ['PENDING_ACCEPTANCE', 'CLOSED'].includes(order.value?.status ?? '') && order.value?.rating === null) ||
  (isDispatcher.value && order.value?.syncStatus === 'FAILED'));
const actionNames: Record<OrderAction, string> = { assign: '派单已保存。', start: '已申请开始维修，正在确认座位下架。', complete: '完工记录已提交，等待报修人验收。', accept: '验收通过，正在确认座位恢复。', reject: '工单已退回继续维修，房间仍保持下架。', cancel: '工单已取消。', rate: '评价已提交，感谢你的反馈。', 'retry-sync': '已重新安排同步，请等待结果。' };

function actorLabel(actorId: string) {
  if (actorId === actor.value?.id) return `${actor.value.name}（当前身份）`;
  if (actorId === 'system' || actorId === 'worker' || actorId === 'm3-worker') return '系统';
  return technicians.value.find(item => item.id === actorId)?.name ?? actorId;
}
function isAccessLost(cause: unknown): boolean {
  return cause instanceof ApiError && [401, 403, 404].includes(cause.status);
}
function clearInaccessibleOrder() {
  // A reassignment or expired identity may revoke access after the page was loaded.
  // Do not retain private details or editable drafts behind an error message.
  order.value = null;
  assigneeId.value = '';
  resolution.value = '';
  rejectReason.value = '';
  cancelReason.value = '';
  retryReason.value = '';
  rating.value = '';
  comment.value = '';
  actionMessage.value = '';
  actionError.value = '';
  needsRefresh.value = true;
}
async function refresh(silent = false) {
  if (busy.value || refreshInFlight) return;
  refreshInFlight = true;
  const currentRead = ++readSequence;
  if (!silent) loading.value = true;
  try {
    const result = await session.api.get(id);
    if (!alive || currentRead !== readSequence || busy.value || (order.value && result.version < order.value.version)) return;
    order.value = result;
    fetchError.value = '';
    needsRefresh.value = false;
    actionError.value = '';
    if (!assigneeId.value) assigneeId.value = result.assigneeId ?? '';
  } catch (cause) {
    if (alive && currentRead === readSequence && !isAbort(cause)) {
      fetchError.value = describeError(cause);
      needsRefresh.value = true;
      if (isAccessLost(cause)) clearInaccessibleOrder();
    }
  }
  finally { refreshInFlight = false; if (alive && !silent) loading.value = false; }
}
async function act(action: OrderAction, fields: Record<string, unknown> = {}) {
  if (!order.value || busy.value || needsRefresh.value || loading.value) return;
  actionError.value = '';
  actionMessage.value = '';
  busy.value = true;
  readSequence += 1; // Any earlier GET must not overwrite this command's newer response.
  try {
    const result = await session.api.act(id, action, { version: order.value.version, ...fields });
    if (!alive) return;
    order.value = result;
    actionMessage.value = actionNames[action];
    resolution.value = '';
    rejectReason.value = '';
    cancelReason.value = '';
    retryReason.value = '';
  } catch (cause) {
    if (!alive || isAbort(cause)) return;
    if (isAccessLost(cause)) {
      clearInaccessibleOrder();
      fetchError.value = describeError(cause);
      return;
    }
    actionError.value = describeError(cause);
    if (cause instanceof ApiError && (cause.status === 409 || cause.status === 0 || cause.status >= 500)) needsRefresh.value = true;
  } finally { if (alive) busy.value = false; }
}
onMounted(() => {
  void refresh();
  pollTimer = setInterval(() => { if (pendingSync.value && order.value?.syncStatus === 'PENDING' && !busy.value && !loading.value && !document.hidden) void refresh(true); }, 4000);
});
onUnmounted(() => { alive = false; if (pollTimer) clearInterval(pollTimer); });
</script>

<template>
  <section aria-label="工单详情">
    <div class="m3-detail-top"><RouterLink to="/m3" class="ui-link"><AppIcon name="arrow-left" :size="15" />返回工单中心</RouterLink><button class="ui-button m3-refresh" :disabled="busy || loading" @click="refresh()">{{ loading ? '刷新中…' : '刷新进度' }}</button></div>
    <div v-if="loading && !order" class="m3-empty ui-panel" role="status"><AppIcon name="clock" :size="27" /><p>正在加载工单详情…</p></div>
    <div v-if="fetchError" class="m3-alert m3-alert--error" role="alert"><div><p>{{ fetchError }}</p><p v-if="order">当前展示的是上次成功加载的信息，请重新加载确认最新状态后再操作。</p></div><button class="ui-button" :disabled="loading" @click="refresh()">重新加载</button></div>
    <template v-if="order">
      <header class="m3-order-heading ui-panel"><div class="m3-order-headline"><div><p class="m3-reference">工单 {{ order.id }}</p><h2>{{ order.title }}</h2><p class="m3-location"><AppIcon name="location" :size="15" />{{ order.roomName || order.roomId }}<span aria-hidden="true">·</span>{{ categoryLabels[order.category] }}</p></div><StatusBadge :status="order.status" /></div>
        <ol v-if="order.status !== 'CANCELLED'" class="m3-steps" aria-label="维修进度"><li v-for="(step, index) in ['已上报', '已派单', '维修中', '待验收', '已完成']" :key="step" :class="{ completed: index < stepIndex, current: index === stepIndex }" :aria-current="index === stepIndex ? 'step' : undefined"><span><AppIcon v-if="index < stepIndex" name="check" :size="13" /><template v-else>{{ index + 1 }}</template></span>{{ step }}</li></ol>
      </header>
      <div v-if="order.escalated" class="m3-alert m3-alert--warning"><AppIcon name="clock" :size="19" /><p><strong>此工单已超时升级</strong>系统已记录升级事项。通知送达仍待公共通知服务接入。</p></div>
      <div v-if="pendingSync" class="m3-alert" :class="order.syncStatus === 'FAILED' ? 'm3-alert--error' : 'm3-alert--info'" role="status"><AppIcon :name="order.syncStatus === 'FAILED' ? 'info' : 'clock'" :size="20" /><div><strong>{{ order.syncStatus === 'FAILED' ? '座位联动尚未完成' : order.status === 'STARTING_REPAIR' ? '正在确认房间座位下架' : '正在确认解除本工单的座位下架' }}</strong><p>{{ order.syncStatus === 'FAILED' ? '请由物业调度核查同步问题；工单会保留在当前状态。' : '页面会自动更新。确认联动结果后，系统才会推进工单状态。' }}</p><p v-if="order.syncError" class="m3-sync-code">同步原因：{{ order.syncError }}</p><p v-if="context?.dependencyMode === 'stub'">本次为模拟依赖响应，不代表真实座位已变化。</p></div></div>
      <p v-if="actionMessage" class="m3-success" role="status"><AppIcon name="check" :size="17" />{{ actionMessage }}</p>
      <div v-if="actionError" class="m3-alert m3-alert--error" role="alert"><div><p>{{ actionError }}</p><p v-if="needsRefresh">请先刷新确认最新状态，避免重复操作。</p></div><button v-if="needsRefresh" class="ui-button" @click="refresh()">刷新并核对</button></div>
      <div class="m3-detail-grid">
        <div class="m3-main-column">
          <section class="m3-section ui-panel"><h3>故障信息</h3><p class="m3-description">{{ order.description }}</p><dl class="m3-facts"><div><dt>报修人</dt><dd>{{ actorLabel(order.reporterId) }}</dd></div><div><dt>维修人员</dt><dd>{{ order.assigneeId ? actorLabel(order.assigneeId) : '等待派单' }}</dd></div><div><dt>上报时间</dt><dd>{{ displayTime(order.createdAt) }}</dd></div><div><dt>{{ finished ? '最近更新' : '处理时限' }}</dt><dd>{{ displayTime(finished ? order.updatedAt : order.dueAt) }}<span v-if="order.escalated && !finished" class="m3-overdue">已升级</span></dd></div></dl></section>
          <section v-if="order.resolution" class="m3-section ui-panel"><h3>维修说明</h3><p class="m3-description">{{ order.resolution }}</p><p v-if="order.status === 'PENDING_ACCEPTANCE'" class="m3-section-note">提交完工不会直接恢复座位。请报修人确认维修结果后进行验收。</p></section>
          <section v-if="order.rating !== null" class="m3-section ui-panel"><h3>报修人评价</h3><p class="m3-rating"><span aria-hidden="true">{{ '★'.repeat(order.rating) }}<span class="m3-empty-stars">{{ '☆'.repeat(5 - order.rating) }}</span></span><strong>{{ order.rating }} / 5 分</strong></p><p class="m3-description">{{ order.comment || '未填写评价内容。' }}</p></section>
          <section v-if="hasActions" class="m3-section m3-action-section ui-panel" aria-labelledby="m3-actions-title"><h3 id="m3-actions-title">处理工单</h3>
            <fieldset :disabled="busy || loading || needsRefresh">
              <form v-if="assignable" class="m3-action-form" @submit.prevent="act('assign', { assigneeId })"><h4>{{ order.status === 'ASSIGNED' ? '调整维修人员' : '安排维修人员' }}</h4><div class="m3-field"><label for="m3-assignee">维修人员</label><select id="m3-assignee" v-model="assigneeId" required><option value="" disabled>请选择维修人员</option><option v-for="person in technicians" :key="person.id" :value="person.id">{{ person.name }}</option></select></div><p class="m3-action-hint">开始维修前可以调整指派。超时记录不会因此被删除。</p><button class="ui-button ui-button--primary" :disabled="!assigneeId || (order.status === 'ASSIGNED' && assigneeId === order.assigneeId)">{{ busy ? '提交中…' : order.status === 'ASSIGNED' ? '确认重新派单' : '确认派单' }}</button></form>
              <form v-if="isAssignedTechnician && order.status === 'ASSIGNED'" class="m3-action-form" @submit.prevent="act('start')"><h4>开始维修</h4><p class="m3-action-hint">系统会先确认该房间座位下架，确认后工单进入“维修中”。</p><button class="ui-button ui-button--primary">申请开始维修</button></form>
              <form v-if="isAssignedTechnician && order.status === 'IN_PROGRESS'" class="m3-action-form" @submit.prevent="act('complete', { resolution: resolution.trim() })"><h4>提交维修结果</h4><div class="m3-field"><label for="m3-resolution">维修说明</label><textarea id="m3-resolution" v-model="resolution" required maxlength="2000" rows="4" placeholder="说明处理措施和维修结果，帮助报修人验收。" /></div><button class="ui-button ui-button--primary" :disabled="!resolution.trim()">提交完工</button></form>
              <div v-if="isReporter && order.status === 'PENDING_ACCEPTANCE'" class="m3-acceptance"><form class="m3-action-form" @submit.prevent="act('accept')"><h4>确认维修结果</h4><p class="m3-action-hint">请确认故障已经解决。验收通过后，系统解除本工单造成的座位下架；其他有效限制会继续保留。</p><button class="ui-button ui-button--primary">确认验收通过</button></form><form class="m3-action-form" @submit.prevent="act('reject', { reason: rejectReason.trim() })"><h4>问题还未解决？</h4><div class="m3-field"><label for="m3-reject-reason">退回原因</label><textarea id="m3-reject-reason" v-model="rejectReason" required maxlength="1000" rows="3" placeholder="说明仍存在的问题，工单将退回继续维修。" /></div><button class="ui-button" :disabled="!rejectReason.trim()">退回维修</button></form></div>
              <form v-if="isReporter && order.status === 'CLOSED' && order.rating === null" class="m3-action-form" @submit.prevent="act('rate', { rating: Number(rating), comment: comment.trim() })"><h4>评价这次维修</h4><p class="m3-action-hint">评价仅相关参与者可见。每张工单只能评价一次。</p><div class="m3-field"><label for="m3-rating">维修评分</label><select id="m3-rating" v-model="rating" required><option value="" disabled>请选择评分</option><option value="5">5 分 · 非常满意</option><option value="4">4 分 · 满意</option><option value="3">3 分 · 一般</option><option value="2">2 分 · 不满意</option><option value="1">1 分 · 很不满意</option></select></div><div class="m3-field"><label for="m3-comment">评价内容 <span>选填</span></label><textarea id="m3-comment" v-model="comment" maxlength="1000" rows="3" placeholder="分享维修体验，不要填写他人的个人信息。" /></div><button class="ui-button ui-button--primary" :disabled="!rating">提交评价</button></form>
              <form v-if="isDispatcher && order.syncStatus === 'FAILED'" class="m3-action-form" @submit.prevent="act('retry-sync', { reason: retryReason.trim() })"><h4>恢复座位同步</h4><p class="m3-action-hint">仅临时网络故障且自动重试已用尽时可以重试。服务端会检查是否符合条件，权限、房间或版本冲突需协调处理。</p><div class="m3-field"><label for="m3-retry-reason">重试处理说明</label><textarea id="m3-retry-reason" v-model="retryReason" required maxlength="1000" rows="3" placeholder="记录已核查或修复的依赖问题。" /></div><button class="ui-button" :disabled="!retryReason.trim()">检查并重新同步</button></form>
              <details v-if="cancellable" class="m3-cancel"><summary>不再需要这次报修？</summary><form class="m3-action-form" @submit.prevent="act('cancel', { reason: cancelReason.trim() })"><div class="m3-field"><label for="m3-cancel-reason">取消原因</label><textarea id="m3-cancel-reason" v-model="cancelReason" required maxlength="1000" rows="3" placeholder="例如：重复上报，或故障已自行恢复。" /></div><p class="m3-action-hint">只有尚未开始维修的工单可以取消。</p><button class="ui-button m3-cancel-button" :disabled="!cancelReason.trim()">确认取消工单</button></form></details>
            </fieldset>
          </section>
          <div v-else-if="!finished && !pendingSync" class="m3-passive-note"><AppIcon name="info" :size="16" /><p>{{ order.status === 'PENDING_ACCEPTANCE' ? '等待报修人验收。' : order.status === 'REPORTED' ? '已收到报修，等待物业调度安排。' : order.status === 'ASSIGNED' ? '已安排维修人员，等待开始维修。' : '维修人员正在处理，请关注进度记录。' }}</p></div>
        </div>
        <aside class="m3-section m3-history ui-panel" aria-labelledby="m3-history-title"><h3 id="m3-history-title">进度记录</h3><ol><li v-for="(entry, index) in [...order.history].reverse()" :key="`${index}-${entry.at}-${entry.action}`"><span class="m3-history-dot" aria-hidden="true"></span><time :datetime="entry.at">{{ displayTime(entry.at) }}</time><h4>{{ actionLabels[entry.action.toUpperCase()] ?? entry.action }}</h4><p v-if="entry.detail" class="m3-history-detail">{{ entry.detail }}</p><p class="m3-history-actor">{{ actorLabel(entry.actorId) }}</p></li></ol><p v-if="!order.history.length" class="m3-section-note">暂无进度记录。</p><p class="m3-timezone">时间均为北京时间</p></aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.m3-detail-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.m3-detail-top > a { font-size: 12px; }
.m3-refresh { min-height: 37px; padding: 7px 12px; font-size: 12px; }
.m3-empty { display: grid; justify-items: center; gap: 15px; color: var(--color-muted); padding: 50px 20px; }
.m3-empty p { margin: 0; font-size: 13px; }
.m3-order-heading { padding: 25px 28px; margin-bottom: 22px; }
.m3-order-headline { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.m3-order-headline > div { min-width: 0; }
.m3-reference { color: var(--color-muted); font-size: 10px; margin: 0 0 10px; overflow-wrap: anywhere; letter-spacing: .03em; }
.m3-order-headline h2 { margin: 0 0 11px; font-size: 22px; overflow-wrap: anywhere; }
.m3-location { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; color: var(--color-muted); font-size: 12px; margin: 0; }
.m3-steps { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; list-style: none; margin: 25px 0 0; padding: 23px 0 0; border-top: 1px solid var(--color-border); }
.m3-steps li { display: flex; align-items: center; gap: 8px; color: #849499; font-size: 12px; }
.m3-steps li > span { display: grid; place-items: center; width: 23px; height: 23px; font-size: 11px; background: #f0f4f4; color: #839498; border: 1px solid #e2e9ea; border-radius: 50%; flex: none; }
.m3-steps li.current, .m3-steps li.completed { color: var(--color-brand); }
.m3-steps li.current > span { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.m3-steps li.completed > span { color: var(--color-brand); background: var(--color-brand-soft); border-color: var(--color-brand-soft); }
.m3-detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 22px; align-items: start; }
.m3-main-column { display: grid; gap: 20px; min-width: 0; }
.m3-section { padding: 24px 26px; min-width: 0; }
.m3-section h3 { margin: 0 0 19px; font-size: 15px; }
.m3-description { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.85; }
.m3-facts { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 25px; margin: 24px 0 0; padding-top: 21px; border-top: 1px solid #edf1f2; }
.m3-facts dt { font-size: 11px; color: var(--color-muted); margin-bottom: 6px; }
.m3-facts dd { margin: 0; font-size: 12px; overflow-wrap: anywhere; }
.m3-overdue { margin-left: 7px; color: #a3642b; font-size: 11px; }
.m3-alert { padding: 15px 18px; border: 1px solid; border-radius: 9px; margin: 0 0 20px; display: flex; align-items: flex-start; gap: 12px; font-size: 12px; line-height: 1.8; }
.m3-alert > svg { margin-top: 3px; }
.m3-alert > div { min-width: 0; }
.m3-alert p { margin: 0; overflow-wrap: anywhere; }
.m3-alert strong { display: block; margin-bottom: 3px; font-weight: 600; }
.m3-alert .ui-button { flex: none; font-size: 12px; margin-left: auto; min-height: 36px; padding: 7px 12px; }
.m3-alert--warning { background: #fffbf3; border-color: #eaddc3; color: #8a6a34; }
.m3-alert--error { background: #fff6f5; border-color: #efd6d2; color: var(--color-danger); }
.m3-alert--info { background: #f0f7f8; border-color: #cfE3e6; color: #35717b; }
.m3-sync-code { font-size: 11px; }
.m3-success { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #2e7758; background: #edf7f0; border: 1px solid #d5e9da; border-radius: 8px; padding: 12px 16px; margin: 0 0 20px; }
.m3-section-note, .m3-action-hint { color: var(--color-muted); font-size: 12px; line-height: 1.8; margin: 0; }
.m3-section-note { margin-top: 16px; }
.m3-action-section fieldset { margin: 0; padding: 0; border: 0; min-width: 0; }
.m3-action-form { display: grid; justify-items: start; gap: 14px; }
.m3-action-form + .m3-action-form, .m3-acceptance > form + form { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--color-border); }
.m3-action-form h4 { font-size: 13px; font-weight: 550; margin: 0; }
.m3-action-form .ui-button { font-size: 13px; }
.m3-field { display: grid; gap: 8px; min-width: 0; width: 100%; }
.m3-field label { font-size: 12px; font-weight: 550; }
.m3-field label span { font-size: 11px; color: var(--color-muted); font-weight: 400; }
.m3-field select, .m3-field textarea { width: 100%; min-width: 0; border: 1px solid var(--color-border); background: #fff; padding: 10px 12px; border-radius: 8px; font-size: 13px; }
.m3-field textarea { resize: vertical; min-height: 90px; line-height: 1.8; }
.m3-cancel { border-top: 1px solid var(--color-border); padding-top: 18px; margin-top: 23px; }
.m3-cancel summary { color: var(--color-muted); cursor: pointer; font-size: 12px; min-height: 32px; padding: 5px 0; }
.m3-cancel form { margin-top: 16px; }
.m3-cancel-button { color: var(--color-danger); }
.m3-rating { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: #bc8a31; margin: 0 0 12px; }
.m3-rating > span { letter-spacing: 3px; font-size: 23px; }
.m3-rating strong { font-size: 13px; font-weight: 550; }
.m3-empty-stars { color: #cabfa9; }
.m3-history { padding: 24px 23px; }
.m3-history ol { list-style: none; padding: 0; margin: 0; }
.m3-history li { position: relative; padding: 0 0 23px 19px; border-left: 1px solid #dce7e9; margin-left: 4px; }
.m3-history li:last-child { border-color: transparent; padding-bottom: 0; }
.m3-history-dot { position: absolute; width: 7px; height: 7px; left: -4px; top: 5px; border-radius: 50%; background: #abc5ca; box-shadow: 0 0 0 4px #fff; }
.m3-history li:first-child .m3-history-dot { background: var(--color-brand); }
.m3-history time { font-size: 10px; color: #879599; }
.m3-history h4 { font-size: 13px; font-weight: 550; margin: 6px 0 7px; }
.m3-history-detail { font-size: 12px; color: var(--color-muted); white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.8; margin: 0 0 5px; }
.m3-history-actor { color: #8b979a; font-size: 10px; margin: 0; overflow-wrap: anywhere; }
.m3-timezone { font-size: 10px; color: var(--color-muted); margin: 24px 0 0; padding-top: 14px; border-top: 1px solid var(--color-border); }
.m3-passive-note { display: flex; gap: 9px; color: var(--color-muted); font-size: 12px; padding: 5px 4px; }
.m3-passive-note p { margin: 0; }
@media (max-width: 850px) { .m3-detail-grid { grid-template-columns: 1fr; } .m3-history { padding: 22px; } }
@media (max-width: 580px) { .m3-order-heading { padding: 22px 16px; } .m3-order-headline { flex-direction: column; gap: 13px; } .m3-order-headline h2 { font-size: 20px; } .m3-steps { gap: 5px; } .m3-steps li { flex-direction: column; align-items: center; text-align: center; gap: 7px; font-size: 10px; } .m3-section { padding: 22px 16px; } .m3-facts { gap: 18px; } .m3-field select, .m3-field textarea { font-size: 16px; } .m3-alert { flex-wrap: wrap; padding: 14px; } .m3-alert .ui-button { margin-left: 0; } .m3-alert > div { flex: 1; min-width: 0; } }
@media (max-width: 350px) { .m3-facts { grid-template-columns: 1fr; } }
</style>
