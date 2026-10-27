<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { ApiError } from '../../../shared/api/client';
import StatusBadge from '../components/StatusBadge.vue';
import { errorMessage, type ActionInput, type Identity, type OrderAction, type WorkOrder } from '../api';
import { actionLabels, categoryLabels, formatTime, historyLabel, shortId } from '../presentation';
import { useM3Session } from '../session';

const { api, identity } = useM3Session();
const route = useRoute();
const id = String(route.params.id);
const order = ref<WorkOrder | null>(null);
const loading = ref(true);
const submitting = ref(false);
const error = ref('');
const actionError = ref('');
const success = ref('');
const technicianError = ref('');
const technicians = ref<Identity[]>([]);
const technicianLoading = ref(false);
const editor = ref<OrderAction | null>(null);
const assigneeId = ref('');
const note = ref('');
const score = ref(5);
const comment = ref('');
const editorElement = ref<HTMLElement | null>(null);
const feedbackElement = ref<HTMLElement | null>(null);
let editingVersion = 0;
let active = true;
let loadSequence = 0;
let loadController: AbortController | null = null;
let actionController: AbortController | null = null;
let technicianController: AbortController | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
const phases = ['已上报', '已派单', '维修处理', '完工验收', '工单完成'];
const phase = computed(() => ({ SUBMITTED:0, ASSIGNED:1, BLOCK_PENDING:2, IN_PROGRESS:2, PENDING_ACCEPTANCE:3, RELEASE_PENDING:3, CLOSED:4, CANCELLED:-1 }[order.value?.status ?? 'SUBMITTED']));
const history = computed(() => [...(order.value?.history ?? [])].sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
const assignable = computed(() => technicians.value.filter(person => person.id !== order.value?.assigneeId));
const acceptingForAnother = computed(() => identity.role === 'admin' && order.value?.reporterId !== identity.id);
const noteRequired = computed(() => editor.value === 'complete' || editor.value === 'reject' || editor.value === 'cancel' || (editor.value === 'accept' && acceptingForAnother.value));
const showNote = computed(() => noteRequired.value || editor.value === 'accept');
const pendingSync = computed(() => order.value?.status === 'BLOCK_PENDING' || order.value?.status === 'RELEASE_PENDING');
const actionDescriptions: Record<OrderAction, string> = {
  assign: '选择负责此工单的维修人员。重新派单不会延长原有处理时限。',
  start: '确认后将请求下架此房间的全部座位。收到下架确认后，工单才会进入维修中。',
  complete: '说明完成的维修内容。提交后由报修人或管理员验收，房间在验收前保持下架。',
  accept: '请确认故障已经排除。通过后发起恢复请求，收到确认后工单才会完成；其他有效限制仍保留。',
  reject: '说明仍存在的问题。工单将返回维修中，保持房间下架，并重新开始维修时限。',
  cancel: '请说明取消原因。取消后工单结束，无法继续派单或维修。',
  rate: '分享这次报修体验。评价仅可提交一次，请确认后提交。',
  'retry-sync': '重新发送此前未完成的同步请求，保持原有来源和版本。不会跳过确认直接修改工单状态。',
};
const actionSuccess: Record<OrderAction, string> = {
  assign: '派单已保存。', start: '开工请求已提交，正在等待房间下架确认。', complete: '完工说明已提交，等待验收。',
  accept: '验收已记录，正在等待本工单限制解除。', reject: '已退回返工，房间继续保持下架。', cancel: '工单已取消。', rate: '评价已保存，感谢你的反馈。', 'retry-sync': '同步重试已提交，请等待回执。',
};
function label(action: OrderAction) { return action === 'assign' && order.value?.assigneeId ? '重新派单' : actionLabels[action]; }
function schedulePoll() {
  clearTimeout(timer);
  if (!active) return;
  timer = setTimeout(async () => {
    if (!document.hidden && !submitting.value) await load(true);
    schedulePoll();
  }, pendingSync.value ? 3000 : 5000);
}
async function load(silent = false) {
  if (submitting.value) return;
  loadController?.abort();
  const abort = new AbortController();
  loadController = abort;
  const current = ++loadSequence;
  if (!silent) loading.value = true;
  try {
    const result = await api.order(id, abort.signal);
    if (!active || abort.signal.aborted || current !== loadSequence) return;
    const previous = order.value?.status;
    order.value = result;
    error.value = '';
    if (previous === 'BLOCK_PENDING' && result.status === 'IN_PROGRESS') success.value = '房间下架已确认，工单已进入维修中。';
    if (previous === 'RELEASE_PENDING' && result.status === 'CLOSED') success.value = '本工单限制已解除，工单已完成。其他有效预约或维修限制不受影响。';
    if (editor.value && !result.allowedActions.includes(editor.value)) {
      editor.value = null;
      actionError.value = '工单状态或权限已经变化，当前操作已关闭。';
    }
  } catch (caught) {
    if (!active || abort.signal.aborted || current !== loadSequence) return;
    error.value = errorMessage(caught);
    if (caught instanceof ApiError && [401,403,404].includes(caught.status)) { order.value = null; editor.value = null; }
  } finally { if (active && current === loadSequence) loading.value = false; }
}
async function loadTechnicians() {
  technicianController?.abort();
  const abort = new AbortController();
  technicianController = abort;
  technicianLoading.value = true;
  technicianError.value = '';
  try {
    const response = await api.technicians(abort.signal);
    if (active && !abort.signal.aborted) technicians.value = response.items;
  } catch (caught) {
    if (active && !abort.signal.aborted) technicianError.value = errorMessage(caught);
  } finally { if (active && !abort.signal.aborted) technicianLoading.value = false; }
}
async function openAction(action: OrderAction) {
  if (!order.value?.allowedActions.includes(action) || submitting.value) return;
  editor.value = action;
  editingVersion = order.value.version;
  assigneeId.value = ''; note.value = ''; comment.value = ''; score.value = 5;
  actionError.value = ''; success.value = '';
  if (action === 'assign') void loadTechnicians();
  await nextTick();
  editorElement.value?.focus();
}
async function submitAction() {
  const currentOrder = order.value;
  const action = editor.value;
  if (submitting.value || !currentOrder || !action || !currentOrder.allowedActions.includes(action)) return;
  actionError.value = '';
  if (noteRequired.value && !note.value.trim()) { actionError.value = '请填写操作说明。'; return; }
  if (action === 'assign' && (!assignable.value.some(person => person.id === assigneeId.value) || technicianError.value)) { actionError.value = '请选择有效的维修人员。'; return; }
  const body: ActionInput = { version: editingVersion };
  if (action === 'assign') body.assigneeId = assigneeId.value;
  if (showNote.value && note.value.trim()) body.note = note.value.trim();
  if (action === 'rate') { body.score = Number(score.value); body.comment = comment.value.trim(); }
  submitting.value = true;
  loadController?.abort();
  loadSequence += 1;
  const abort = new AbortController();
  actionController = abort;
  let conflict = false;
  try {
    const result = await api.action(id, action, body, abort.signal);
    if (!active || abort.signal.aborted) return;
    order.value = result;
    editor.value = null;
    success.value = actionSuccess[action];
    error.value = '';
    await nextTick(); feedbackElement.value?.focus();
  } catch (caught) {
    if (!active || abort.signal.aborted) return;
    actionError.value = errorMessage(caught);
    // Refresh before allowing another mutation after uncertain/conflicting responses.
    conflict = true;
    editor.value = null;
    await nextTick(); feedbackElement.value?.focus();
  } finally {
    if (active) {
      submitting.value = false;
      if (conflict) await load(true);
      schedulePoll();
    }
  }
}
onMounted(async () => { await load(); if (active) schedulePoll(); });
onBeforeUnmount(() => { active = false; loadSequence += 1; clearTimeout(timer); loadController?.abort(); actionController?.abort(); technicianController?.abort(); });
</script>

<template>
  <section aria-labelledby="order-title">
    <div class="detail-navigation"><RouterLink to="/m3" class="back-link"><AppIcon name="arrow-left" :size="15" />返回工单工作台</RouterLink><button class="refresh-button" :disabled="loading || submitting" @click="load()"><AppIcon name="clock" :size="14" />{{ loading ? '更新中' : '刷新进度' }}</button></div>
    <div v-if="loading && !order" class="m3-empty ui-panel" role="status"><h1 id="order-title">正在加载工单</h1><p>正在获取详情与最新处理进度。</p></div>
    <div v-if="error" class="m3-alert" role="alert">{{ error }}<button class="ui-button" :disabled="loading || submitting" @click="load()">重新加载</button></div>
    <div v-if="!loading && !order" class="m3-empty ui-panel"><AppIcon name="shield" :size="30" /><h1 id="order-title">暂时无法查看工单</h1><p>请确认当前身份，或返回工作台查看有权访问的记录。</p><RouterLink to="/m3" class="ui-button">返回工作台</RouterLink></div>
    <div v-if="success || actionError" ref="feedbackElement" tabindex="-1" class="feedback" :class="{ 'is-error': actionError }" :role="actionError ? 'alert' : 'status'"><AppIcon :name="actionError ? 'info' : 'check'" :size="18" /><span>{{ actionError || success }}</span></div>
    <template v-if="order">
      <header class="detail-heading"><div><p class="m3-eyebrow">WORK ORDER · #{{ shortId(order.id) }}</p><h1 id="order-title">{{ order.title }}</h1><p><AppIcon name="location" :size="15" />{{ order.roomName }}<span>·</span>{{ categoryLabels[order.category] }}</p></div><StatusBadge :status="order.status" /></header>
      <div v-if="order.status !== 'CANCELLED'" class="progress-track" aria-label="工单处理阶段"><div v-for="(name, index) in phases" :key="name" class="progress-step" :class="{ passed: index < phase, current: index === phase }" :aria-current="index === phase ? 'step' : undefined"><span class="step-circle"><AppIcon v-if="index < phase" name="check" :size="13" /><template v-else>{{ index + 1 }}</template></span><span>{{ name }}</span></div></div>
      <div v-if="pendingSync" class="sync-banner" :class="{ 'sync-failed': order.sync?.status === 'failed' }" role="status"><AppIcon name="clock" :size="22" /><div><strong>{{ order.status === 'BLOCK_PENDING' ? '等待房间下架确认' : '等待本工单限制解除' }}</strong><p v-if="order.sync?.status === 'failed'">同步未能完成，已尝试 {{ order.sync.attempts }} 次。{{ order.sync.retryable ? '管理员可重试同步。' : '请由管理员检查依赖服务或同步配置。' }}</p><p v-else>服务正在同步，请稍等。页面会自动刷新，在收到确认前不会提前完成状态切换。</p><p v-if="order.sync?.error" class="sync-error-detail">{{ order.sync.error }}</p></div></div>
      <div v-if="order.escalated && !['CLOSED','CANCELLED'].includes(order.status)" class="escalation-banner"><AppIcon name="clock" :size="16" /><span>此工单已超时升级，已进入管理员待办，请优先跟进。</span></div>
      <div class="detail-grid"><div class="detail-main">
        <section class="content-card ui-panel"><h2><AppIcon name="wrench" :size="18" />报修详情</h2><p class="description">{{ order.description }}</p><dl class="metadata"><div><dt>报修人</dt><dd>{{ order.reporterName }}</dd></div><div><dt>维修人员</dt><dd>{{ order.assigneeName || '等待分配' }}</dd></div><div><dt>提交时间</dt><dd>{{ formatTime(order.createdAt) }}</dd></div><div><dt>{{ order.dueAt ? '当前处理时限' : '最近更新' }}</dt><dd>{{ formatTime(order.dueAt || order.updatedAt) }}</dd></div></dl></section>
        <section v-if="order.allowedActions.length" class="content-card action-card ui-panel" aria-labelledby="action-title"><h2 id="action-title"><AppIcon name="shield" :size="18" />当前可操作</h2><p class="section-intro">根据你的身份与工单进度，选择下一步。</p><div class="action-buttons"><button v-for="action in order.allowedActions" :key="action" type="button" class="ui-button" :class="{ 'ui-button--primary': !['cancel','reject'].includes(action), 'danger-button': ['cancel','reject'].includes(action), 'is-selected': editor === action }" :disabled="submitting" :aria-expanded="editor === action" aria-controls="m3-action-form" @click="openAction(action)">{{ label(action) }}</button></div>
          <form v-if="editor" id="m3-action-form" ref="editorElement" tabindex="-1" class="action-editor" :aria-busy="submitting" @submit.prevent="submitAction"><h3>{{ label(editor) }}</h3><p class="action-description">{{ actionDescriptions[editor] }}</p><fieldset :disabled="submitting"><legend class="ui-sr-only">{{ label(editor) }}所需信息</legend>
            <template v-if="editor === 'assign'"><p v-if="technicianLoading" role="status" class="minor-note">正在读取维修人员目录…</p><div v-if="technicianError" class="m3-alert" role="alert">{{ technicianError }}<button type="button" class="ui-button" @click="loadTechnicians">重新加载</button></div><label class="m3-field">维修人员<select v-model="assigneeId" required :disabled="technicianLoading || Boolean(technicianError)"><option value="" disabled>请选择维修人员</option><option v-for="person in assignable" :key="person.id" :value="person.id">{{ person.name }}</option></select></label><p v-if="!technicianLoading && !technicianError && !assignable.length" class="minor-note">当前没有其他可分配的维修人员。</p></template>
            <label v-if="showNote" class="m3-field">{{ editor === 'complete' ? '完工说明' : editor === 'reject' ? '返工原因' : editor === 'cancel' ? '取消原因' : '验收说明' }}{{ noteRequired ? '（必填）' : '（选填）' }}<textarea v-model="note" :required="noteRequired" maxlength="2000" rows="4" :placeholder="editor === 'complete' ? '说明修复内容和处理结果' : '说明本次操作的原因或检查结果'"></textarea><small>最多 2000 字。{{ editor === 'accept' && acceptingForAnother ? '管理员代验必须填写说明。' : '' }}</small></label>
            <template v-if="editor === 'rate'"><fieldset class="rating-options"><legend>本次维修体验</legend><label v-for="value in [1,2,3,4,5]" :key="value" :class="{ selected: score === value }"><input v-model="score" type="radio" name="score" :value="value" required><span>{{ value }}<span aria-hidden="true"> ★</span></span></label></fieldset><label class="m3-field">评价内容（选填）<textarea v-model="comment" maxlength="2000" rows="4" placeholder="说说修复效果或服务体验"></textarea></label></template>
            <div class="editor-actions"><button type="button" class="ui-button" @click="editor = null">返回</button><button type="submit" class="ui-button ui-button--primary" :disabled="submitting || (editor === 'assign' && (technicianLoading || !assignable.length || Boolean(technicianError)))">{{ submitting ? '正在提交…' : `确认${label(editor)}` }}</button></div>
          </fieldset></form>
        </section>
        <section v-else class="passive-note ui-panel"><AppIcon name="info" :size="18" /><p>{{ order.status === 'CLOSED' ? '工单已完成。感谢你对校园空间的照顾。' : order.status === 'CANCELLED' ? '工单已取消，处理流程已经结束。' : '当前阶段无需你操作，后续进度会自动更新。' }}</p></section>
        <section v-if="order.rating" class="content-card review-card ui-panel"><h2><AppIcon name="check" :size="18" />报修评价</h2><div class="rating-display"><span :aria-label="`${order.rating.score}分，满分5分`">{{ '★'.repeat(order.rating.score) }}<span class="unfilled-stars" aria-hidden="true">{{ '★'.repeat(5 - order.rating.score) }}</span></span><small>{{ formatTime(order.rating.createdAt) }}</small></div><p v-if="order.rating.comment" class="description">{{ order.rating.comment }}</p><p v-else class="minor-note">报修人未填写文字评价。</p></section>
      </div><aside class="timeline-card ui-panel" aria-labelledby="timeline-title"><div class="timeline-heading"><h2 id="timeline-title">处理记录</h2><span>{{ order.history.length }}</span></div><ol class="timeline"><li v-for="(item, index) in history" :key="item.id" :class="{ latest: index === 0 }"><span class="timeline-dot" aria-hidden="true"></span><h3>{{ historyLabel(item.action) }}</h3><p v-if="item.note" class="timeline-note">{{ item.note }}</p><div class="timeline-meta"><span>{{ item.actorName || '系统' }}</span><time :datetime="item.createdAt">{{ formatTime(item.createdAt) }}</time></div></li></ol><p v-if="!history.length" class="minor-note">暂无处理记录。</p><p class="timeline-footnote">时间按当前设备时区显示<br>完整操作记录由服务端保存</p></aside></div>
    </template>
  </section>
</template>

<style scoped>
.detail-navigation { display:flex; justify-content:space-between; gap:15px; align-items:center; margin-bottom:21px; }
.back-link { display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--color-muted); text-decoration:none; min-height:35px; }
.refresh-button { background:none; border:0; display:flex; align-items:center; gap:5px; min-height:40px; color:var(--color-muted); font-size:11px; }
.detail-heading { display:flex; gap:20px; justify-content:space-between; align-items:center; margin-bottom:24px; }
.detail-heading > div { min-width:0; }
.detail-heading h1 { font-size:clamp(23px,2.7vw,30px); margin:0 0 11px; overflow-wrap:anywhere; }
.detail-heading > div > p:last-child { display:flex; gap:7px; align-items:center; flex-wrap:wrap; color:var(--color-muted); font-size:12px; margin:0; }
.detail-heading > div > p:last-child > span { color:#b2c0c2; }
.progress-track { display:flex; justify-content:space-between; gap:10px; padding:22px 26px; border:1px solid var(--color-border); background:var(--color-surface); border-radius:11px; margin-bottom:22px; }
.progress-step { display:flex; align-items:center; gap:9px; color:#8d9c9f; font-size:12px; position:relative; }
.step-circle { width:25px; height:25px; border:1px solid #d8e2e4; color:#8b9da0; border-radius:50%; display:grid; place-items:center; font-size:10px; flex-shrink:0; }
.progress-step.current { color:var(--color-brand); font-weight:600; }
.progress-step.current .step-circle { color:#fff; background:var(--color-brand); border-color:var(--color-brand); box-shadow:0 0 0 4px #edf6f6; }
.progress-step.passed .step-circle { background:#eaf3f2; border-color:#eaf3f2; color:#4c8a80; }
.sync-banner { display:flex; gap:13px; align-items:flex-start; border:1px solid #d9cfe3; padding:18px 20px; background:#f7f3fa; color:#755686; border-radius:10px; margin-bottom:20px; }
.sync-banner strong { font-size:13px; }
.sync-banner p { font-size:12px; line-height:1.8; margin:4px 0 0; }
.sync-failed { color:#99555b; background:#fff4f4; border-color:#e7d1d3; }
.sync-error-detail { overflow-wrap:anywhere; }
.escalation-banner { display:flex; gap:8px; align-items:flex-start; margin:0 0 18px; padding:11px 15px; border:1px solid #eddfbc; border-radius:8px; background:#fffbf1; color:#8f6d30; font-size:12px; }
.detail-grid { display:grid; grid-template-columns:minmax(0,1fr) 290px; gap:23px; align-items:start; }
.detail-main { display:grid; gap:20px; min-width:0; }
.content-card { padding:25px; }
.content-card h2 { display:flex; align-items:center; gap:8px; font-size:15px; margin:0 0 20px; }
.content-card h2 .app-icon { color:#658e95; }
.description { white-space:pre-wrap; overflow-wrap:anywhere; font-size:14px; line-height:1.9; margin:0; }
.metadata { display:grid; grid-template-columns:1fr 1fr; gap:21px; padding-top:23px; margin:24px 0 0; border-top:1px solid #e9eeee; }
.metadata dt { font-size:11px; color:var(--color-muted); margin-bottom:6px; }
.metadata dd { font-size:13px; margin:0; overflow-wrap:anywhere; }
.section-intro { font-size:12px; color:var(--color-muted); margin:-8px 0 20px; }
.action-buttons { display:flex; flex-wrap:wrap; gap:10px; }
.action-buttons .ui-button { font-size:12px; padding:9px 13px; }
.danger-button { color:#a05557; border-color:#e4d3d4; }
.is-selected { box-shadow:0 0 0 3px #e1eeef; }
.action-editor { border-top:1px solid #e2e9ea; margin-top:24px; padding-top:23px; outline:none; }
.action-editor h3 { font-size:15px; margin:0 0 8px; }
.action-description { font-size:12px; color:var(--color-muted); margin:0 0 20px; line-height:1.85; }
.action-editor > fieldset { padding:0; margin:0; border:0; min-width:0; display:grid; gap:18px; }
.editor-actions { display:flex; justify-content:flex-end; flex-wrap:wrap; gap:9px; margin-top:4px; }
.editor-actions .ui-button { font-size:12px; }
.rating-options { padding:0; margin:0; border:0; display:flex; gap:9px; flex-wrap:wrap; }
.rating-options legend { font-size:13px; margin-bottom:12px; }
.rating-options label { cursor:pointer; display:flex; align-items:center; gap:5px; padding:8px 9px; border:1px solid #dde4e4; border-radius:7px; font-size:12px; min-height:44px; }
.rating-options label.selected { background:#fff8e8; border-color:#dbbd70; color:#87661e; }
.rating-options input { accent-color:var(--color-brand); margin:0; }
.passive-note { display:flex; align-items:flex-start; gap:10px; padding:20px 25px; color:var(--color-muted); }
.passive-note p { font-size:12px; margin:0; }
.minor-note { font-size:12px; color:var(--color-muted); margin:0; }
.rating-display { display:flex; justify-content:space-between; gap:15px; align-items:center; margin-bottom:12px; }
.rating-display > span { color:#c09a42; font-size:21px; letter-spacing:3px; }
.unfilled-stars { color:#dfe6e6; }
.rating-display small { color:var(--color-muted); font-size:10px; }
.feedback { display:flex; align-items:flex-start; gap:10px; color:#2b7561; background:#eef7f2; border:1px solid #cfe5da; padding:14px 17px; border-radius:9px; font-size:13px; margin-bottom:20px; }
.feedback.is-error { color:var(--color-danger); background:#fff5f5; border-color:#e6c5c7; }
.timeline-card { padding:24px; }
.timeline-heading { display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; }
.timeline-heading h2 { font-size:15px; margin:0; }
.timeline-heading > span { font-size:10px; color:var(--color-muted); background:#edf2f3; padding:1px 6px; border-radius:4px; }
.timeline { list-style:none; padding:0; margin:0; }
.timeline li { position:relative; padding:0 0 25px 23px; border-left:1px solid #dfe7e8; margin-left:4px; }
.timeline li:last-child { border-left-color:transparent; padding-bottom:0; }
.timeline-dot { position:absolute; left:-4px; top:5px; width:7px; height:7px; background:#c9d6d8; border-radius:50%; }
.timeline .latest .timeline-dot { background:var(--color-brand); box-shadow:0 0 0 4px #eaf3f3; }
.timeline h3 { font-size:12px; margin:0 0 8px; line-height:1.7; overflow-wrap:anywhere; }
.timeline-note { font-size:11px; line-height:1.8; color:var(--color-muted); margin:0 0 8px; white-space:pre-wrap; overflow-wrap:anywhere; }
.timeline-meta { display:flex; flex-wrap:wrap; gap:5px 10px; font-size:10px; color:#8b9b9f; }
.timeline-footnote { border-top:1px solid #e8eeee; padding-top:18px; margin:22px 0 0; font-size:10px; color:#89999e; line-height:1.9; }
@media(max-width:950px) { .detail-grid { grid-template-columns:minmax(0,1fr) 240px; gap:18px; } .timeline-card { padding:20px; } .progress-track { padding:22px 18px; } .progress-step { gap:6px; font-size:11px; } }
@media(max-width:750px) { .detail-grid { grid-template-columns:1fr; } .progress-track { gap:5px; padding:20px 12px; } .progress-step { flex-direction:column; align-items:center; gap:9px; flex:1; font-size:10px; text-align:center; } .detail-heading { align-items:flex-start; flex-wrap:wrap; gap:14px; } .content-card { padding:21px; } .timeline-card { padding:23px; } }
@media(max-width:400px) { .content-card { padding:18px; } .metadata { gap:17px 12px; } .metadata dd { font-size:12px; } .progress-track { padding-inline:8px; } .progress-step { font-size:9px; } .rating-options { gap:6px; } .rating-options label { padding:8px; } .rating-display { flex-wrap:wrap; } }
</style>
