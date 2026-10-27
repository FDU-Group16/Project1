<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { errorMessage, type Category, type Room } from '../api';
import { categoryLabels } from '../presentation';
import { useM3Session } from '../session';

const { api } = useM3Session();
const router = useRouter();
const rooms = ref<Room[]>([]);
const loading = ref(true);
const submitting = ref(false);
const error = ref('');
const directoryError = ref('');
const alert = ref<HTMLElement | null>(null);
const roomId = ref('');
const category = ref<Category>('facilities');
const title = ref('');
const description = ref('');
let active = true;
let roomController: AbortController | null = null;
let submitController: AbortController | null = null;
let lastRequest: { fingerprint: string; key: string } | null = null;
async function loadRooms() {
  roomController?.abort();
  const abort = new AbortController();
  roomController = abort;
  loading.value = true;
  directoryError.value = '';
  try {
    const response = await api.rooms(abort.signal);
    if (active && !abort.signal.aborted) rooms.value = response.items;
  } catch (caught) {
    if (active && !abort.signal.aborted) directoryError.value = errorMessage(caught);
  } finally { if (active && !abort.signal.aborted) loading.value = false; }
}
async function submit() {
  if (submitting.value || loading.value || !rooms.value.length || directoryError.value) return;
  error.value = '';
  if (!title.value.trim() || !description.value.trim() || !rooms.value.some(room => room.id === roomId.value)) {
    error.value = '请选择报修房间，并填写有效的问题标题和详细描述。';
    await nextTick(); alert.value?.focus(); return;
  }
  submitting.value = true;
  const body = { roomId: roomId.value, category: category.value, title: title.value.trim(), description: description.value.trim() };
  const fingerprint = JSON.stringify(body);
  if (!lastRequest || lastRequest.fingerprint !== fingerprint) lastRequest = { fingerprint, key: crypto.randomUUID() };
  const abort = new AbortController();
  submitController = abort;
  try {
    const result = await api.create(body, lastRequest.key, abort.signal);
    if (active && !abort.signal.aborted) await router.push(`/m3/work-orders/${encodeURIComponent(result.id)}`);
  } catch (caught) {
    if (active && !abort.signal.aborted) {
      error.value = `${errorMessage(caught)} 如刚才的请求已经送达，保持内容不变重试不会重复创建工单。`;
      await nextTick(); alert.value?.focus();
    }
  } finally { if (active) submitting.value = false; }
}
function guardUnload(event: BeforeUnloadEvent) {
  if (submitting.value) { event.preventDefault(); event.returnValue = ''; }
}
onMounted(() => { void loadRooms(); window.addEventListener('beforeunload', guardUnload); });
onBeforeUnmount(() => { active = false; roomController?.abort(); submitController?.abort(); window.removeEventListener('beforeunload', guardUnload); });
</script>

<template>
  <section aria-labelledby="new-order-title">
    <RouterLink to="/m3" class="back-link"><AppIcon name="arrow-left" :size="15" />返回工单工作台</RouterLink>
    <header class="page-heading"><p class="m3-eyebrow">NEW REPAIR REQUEST</p><h1 id="new-order-title">告诉我们，哪里需要修复？</h1><p>描述清楚问题，帮助维修人员更快找到解决办法。</p></header>
    <div class="form-layout">
      <form class="report-form ui-panel" :aria-busy="submitting" @submit.prevent="submit">
        <div class="form-heading"><span class="step-number">01</span><div><h2>填写报修信息</h2><p>以下信息均为必填项</p></div></div>
        <div v-if="error" ref="alert" class="m3-alert" role="alert" tabindex="-1">{{ error }}</div>
        <div v-if="directoryError" class="m3-alert" role="alert">房间目录加载失败：{{ directoryError }}<button type="button" class="ui-button" @click="loadRooms">重试加载房间</button></div>
        <p v-if="loading" class="directory-note" role="status">正在加载可报修房间…</p>
        <p v-else-if="!directoryError && !rooms.length" class="directory-note" role="status">当前没有可报修的房间。请等待管理员配置后重试。</p>
        <fieldset :disabled="submitting || loading" class="form-fields">
          <legend class="ui-sr-only">报修内容</legend>
          <div class="field-pair"><label class="m3-field">报修房间<select v-model="roomId" required :disabled="!rooms.length || Boolean(directoryError)"><option value="" disabled>请选择问题所在房间</option><option v-for="room in rooms" :key="room.id" :value="room.id">{{ room.name }}</option></select></label><label class="m3-field">故障分类<select v-model="category" required><option v-for="(label, value) in categoryLabels" :key="value" :value="value">{{ label }}</option></select></label></div>
          <label class="m3-field">问题标题<input v-model="title" type="text" maxlength="120" required placeholder="例如：靠窗区域的照明灯持续闪烁" aria-describedby="title-help"><small id="title-help">用一句话概括问题，最多 120 字。</small></label>
          <label class="m3-field">详细描述<textarea v-model="description" maxlength="4000" required rows="7" placeholder="请描述具体位置、出现时间、故障表现，以及是否影响正常使用。" aria-describedby="description-help"></textarea><span class="description-help"><small id="description-help">请勿填写手机号、密码等与维修无关的个人信息。</small><small>{{ description.length }} / 4000</small></span></label>
          <div class="submit-row"><p><AppIcon name="shield" :size="15" />提交后可在工作台跟进进度</p><button type="submit" class="ui-button ui-button--primary" :disabled="submitting || loading || !rooms.length || Boolean(directoryError)">{{ submitting ? '正在提交…' : '提交报修' }}<AppIcon v-if="!submitting" name="arrow-right" :size="16" /></button></div>
        </fieldset>
      </form>
      <aside class="form-aside" aria-label="报修说明">
        <div class="care-illustration"><div class="illustration-ring"><AppIcon name="wrench" :size="37" /></div><span class="illustration-spark">+</span><span class="illustration-dot"></span></div>
        <h2>让问题被看见<br>让空间更好一点</h2><p>每一次反馈，都是对校园公共空间的一份照顾。</p>
        <ol class="next-steps"><li><span>1</span><div><strong>报修与派单</strong><p>管理员确认问题，安排维修人员。</p></div></li><li><span>2</span><div><strong>维修与跟进</strong><p>维修开工前同步房间下架，进度随时可查。</p></div></li><li><span>3</span><div><strong>验收与评价</strong><p>确认修复效果后验收，完成后留下评价。</p></div></li></ol>
        <div class="urgent-note"><AppIcon name="info" :size="16" /><p>如发现漏电、冒烟等紧急危险，请先远离现场，并联系校园值班人员。</p></div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.back-link { display:inline-flex; align-items:center; gap:6px; color:var(--color-muted); font-size:12px; text-decoration:none; min-height:35px; margin-bottom:15px; }
.page-heading { margin-bottom:28px; }
.page-heading h1 { font-size:clamp(24px,3vw,31px); margin:0 0 10px; }
.page-heading > p:last-child { font-size:13px; color:var(--color-muted); margin:0; }
.form-layout { display:grid; grid-template-columns:minmax(0,1fr) 245px; gap:32px; align-items:start; }
.report-form { padding:28px; }
.form-heading { display:flex; gap:12px; align-items:center; margin-bottom:25px; padding-bottom:22px; border-bottom:1px solid #e8eeee; }
.step-number { display:grid; place-items:center; width:35px; height:35px; border-radius:9px; background:var(--color-brand-soft); color:var(--color-brand); font-size:12px; font-weight:650; }
.form-heading h2 { font-size:16px; margin:0 0 3px; }
.form-heading p { font-size:11px; margin:0; color:var(--color-muted); }
.form-fields { padding:0; border:0; margin:0; min-width:0; display:grid; gap:23px; }
.field-pair { display:grid; grid-template-columns:1.2fr 1fr; gap:18px; }
.description-help { display:flex; justify-content:space-between; gap:12px; }
.description-help small:last-child { white-space:nowrap; }
.submit-row { display:flex; justify-content:space-between; gap:16px; align-items:center; padding-top:18px; border-top:1px solid #e8eeee; }
.submit-row p { display:flex; align-items:center; gap:6px; margin:0; font-size:10px; color:var(--color-muted); }
.submit-row .ui-button { flex-shrink:0; }
.directory-note { font-size:12px; color:var(--color-muted); }
.form-aside { padding:5px 0 0; }
.care-illustration { height:125px; width:160px; position:relative; margin-bottom:20px; }
.illustration-ring { display:grid; place-items:center; height:100px; width:100px; border:1px solid #cce2e1; background:#edf6f4; color:#458a83; border-radius:32px; transform:rotate(-8deg); position:absolute; top:12px; left:14px; }
.illustration-ring .app-icon { transform:rotate(8deg); }
.illustration-spark { position:absolute; left:121px; top:3px; color:#b4a278; font-size:26px; }
.illustration-dot { position:absolute; width:10px; height:10px; border-radius:50%; left:130px; top:83px; background:#cfdfd9; }
.form-aside > h2 { font-size:20px; line-height:1.55; margin-bottom:13px; }
.form-aside > p { color:var(--color-muted); font-size:12px; line-height:1.9; }
.next-steps { list-style:none; padding:0; margin:27px 0; display:grid; gap:21px; }
.next-steps li { display:flex; gap:11px; align-items:flex-start; }
.next-steps li > span { width:23px; height:23px; display:grid; place-items:center; border:1px solid #d5e3e4; border-radius:50%; font-size:10px; color:#638c91; flex-shrink:0; }
.next-steps strong { font-size:12px; font-weight:600; }
.next-steps p { font-size:11px; color:var(--color-muted); line-height:1.8; margin:4px 0 0; }
.urgent-note { border-top:1px solid var(--color-border); padding-top:20px; display:flex; gap:8px; color:#7b8e92; }
.urgent-note p { font-size:11px; line-height:1.8; margin:0; }
@media(max-width:900px) { .form-layout { grid-template-columns:minmax(0,1fr) 200px; gap:22px; } .report-form { padding:23px; } .submit-row { align-items:flex-start; flex-direction:column; } .submit-row .ui-button { align-self:flex-end; } }
@media(max-width:700px) { .form-layout { grid-template-columns:1fr; } .form-aside { display:none; } .report-form { padding:20px; } }
@media(max-width:450px) { .field-pair { grid-template-columns:1fr; gap:23px; } .description-help { flex-wrap:wrap; gap:4px; } .description-help small:last-child { margin-left:auto; } .submit-row .ui-button { width:100%; } }
</style>
