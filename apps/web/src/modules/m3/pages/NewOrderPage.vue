<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { ApiError, describeError, isAbort } from '../api';
import { categoryLabels } from '../labels';
import { useM3Session } from '../session';
import type { NewOrder } from '../types';

const session = useM3Session();
const { actor, rooms, pendingCreate } = session;
const router = useRouter();
const form = reactive<NewOrder>(pendingCreate.value ? { ...pendingCreate.value.payload } : { roomId: '', title: '', description: '', category: 'other' });
const submitting = ref(false);
const error = ref('');
const uncertain = computed(() => pendingCreate.value?.uncertain === true);
const canReport = computed(() => actor.value?.roles.includes('student'));
let alive = true;
onUnmounted(() => { alive = false; });
function makeKey() {
  // crypto.getRandomValues is available even on an HTTP localhost-style development origin.
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return `m3-${Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')}`;
}
async function submit() {
  if (submitting.value || !canReport.value) return;
  error.value = '';
  if (!uncertain.value && (!form.roomId || !form.title.trim() || !form.description.trim())) { error.value = '请选择房间，并填写故障标题和详细描述。'; return; }
  const payload = uncertain.value && pendingCreate.value ? pendingCreate.value.payload : { ...form, title: form.title.trim(), description: form.description.trim() };
  if (!pendingCreate.value || JSON.stringify(pendingCreate.value.payload) !== JSON.stringify(payload)) pendingCreate.value = { key: makeKey(), payload, uncertain: false };
  const attempt = pendingCreate.value;
  const currentIdentity = session.generation.value;
  attempt.uncertain = true;
  submitting.value = true;
  try {
    const order = await session.api.create(attempt.payload, attempt.key);
    if (currentIdentity !== session.generation.value) return;
    pendingCreate.value = null;
    if (!alive) return;
    await router.push({ name: 'm3-detail', params: { id: order.id } });
  } catch (cause) {
    if (currentIdentity !== session.generation.value || isAbort(cause)) return;
    attempt.uncertain = !(cause instanceof ApiError) || cause.status === 0 || cause.status >= 500;
    if (alive) error.value = describeError(cause);
  } finally { if (alive) submitting.value = false; }
}
</script>

<template>
  <section v-if="!canReport" class="m3-no-access ui-panel"><AppIcon name="shield" :size="28" /><h2>当前身份不能上报故障</h2><p>请使用报修人身份上报；调度和维修身份用于处理工单。</p><RouterLink to="/m3" class="ui-button">返回工单中心</RouterLink></section>
  <section v-else aria-labelledby="m3-new-title">
    <RouterLink to="/m3" class="m3-back ui-link"><AppIcon name="arrow-left" :size="15" />返回工单中心</RouterLink>
    <div class="m3-page-heading"><h2 id="m3-new-title">上报故障</h2><p>把问题描述清楚，帮助维修人员更快找到原因。</p></div>
    <div class="m3-create-grid">
      <form class="m3-form ui-panel" aria-label="故障上报表单" @submit.prevent="submit">
        <p v-if="uncertain && !submitting" class="m3-notice" role="status">上次提交结果尚未确认。内容已暂时锁定，请点击“确认并重试上报”。重试沿用原请求标识，不会创建重复工单。</p>
        <fieldset :disabled="submitting || uncertain">
          <div class="m3-field"><label for="m3-room">故障位置 <span>必填</span></label><select id="m3-room" v-model="form.roomId" required><option value="" disabled>请选择房间</option><option v-for="room in rooms" :key="room.id" :value="room.id">{{ room.name }}</option></select><p v-if="!rooms.length" class="m3-hint">当前没有可报修的房间，请联系维护者核查目录。</p></div>
          <div class="m3-field"><label for="m3-category">故障分类 <span>必填</span></label><select id="m3-category" v-model="form.category" required><option v-for="(label, category) in categoryLabels" :key="category" :value="category">{{ label }}</option></select></div>
          <div class="m3-field"><label for="m3-title">故障标题 <span>必填</span></label><input id="m3-title" v-model="form.title" required maxlength="120" placeholder="例如：自习室靠窗灯具无法点亮" /><div class="m3-field-footer"><p class="m3-hint">用一句话说明问题。</p><span>{{ form.title.length }}/120</span></div></div>
          <div class="m3-field"><label for="m3-description">详细描述 <span>必填</span></label><textarea id="m3-description" v-model="form.description" required maxlength="2000" rows="6" placeholder="请描述具体位置、故障现象、发现时间，以及对使用的影响。" /><div class="m3-field-footer"><p class="m3-hint">无需填写姓名、手机号或其他个人信息。</p><span>{{ form.description.length }}/2000</span></div></div>
        </fieldset>
        <p v-if="error" class="m3-error" role="alert">{{ error }}</p>
        <div class="m3-form-actions"><RouterLink to="/m3" class="ui-button" :aria-disabled="submitting" @click="submitting && $event.preventDefault()">返回</RouterLink><button class="ui-button ui-button--primary" type="submit" :disabled="submitting || !rooms.length">{{ submitting ? '正在提交…' : uncertain ? '确认并重试上报' : '提交报修' }}<AppIcon v-if="!submitting" name="arrow-right" :size="16" /></button></div>
      </form>
      <aside class="m3-guide ui-panel" aria-label="报修流程说明"><span class="m3-guide-icon"><AppIcon name="wrench" :size="24" /></span><h3>接下来会发生什么</h3><ol><li><strong>物业派单</strong><p>调度人员查看故障，安排维修人员。</p></li><li><strong>维修与跟进</strong><p>维修开始前，系统确认房间座位下架。</p></li><li><strong>由你验收</strong><p>完工后检查维修结果。问题未解决，可以退回继续维修。</p></li></ol><p class="m3-guide-note">存在触电、漏水等紧急危险时，请同时联系现场管理人员，避免靠近危险设施。</p></aside>
    </div>
  </section>
</template>

<style scoped>
.m3-back { font-size: 12px; margin-bottom: 18px; }
.m3-page-heading { margin-bottom: 23px; }
.m3-page-heading h2 { font-size: 23px; margin: 0 0 9px; }
.m3-page-heading p { font-size: 13px; color: var(--color-muted); margin: 0; }
.m3-create-grid { display: grid; grid-template-columns: minmax(0, 1fr) 270px; align-items: start; gap: 24px; }
.m3-form { padding: 26px; }
.m3-form fieldset { padding: 0; border: 0; margin: 0; min-width: 0; display: grid; gap: 23px; }
.m3-field { display: grid; gap: 8px; min-width: 0; }
.m3-field label { font-size: 13px; font-weight: 550; }
.m3-field label span { color: var(--color-muted); font-size: 10px; margin-left: 6px; font-weight: 400; }
.m3-field input, .m3-field select, .m3-field textarea { width: 100%; min-width: 0; padding: 11px 12px; border: 1px solid var(--color-border); border-radius: 8px; background: #fff; font-size: 14px; }
.m3-field textarea { resize: vertical; min-height: 150px; line-height: 1.8; }
.m3-field input:disabled, .m3-field select:disabled, .m3-field textarea:disabled { background: #f5f8f8; color: var(--color-muted); }
.m3-field-footer { display: flex; gap: 15px; justify-content: space-between; align-items: flex-start; font-size: 11px; color: var(--color-muted); }
.m3-field-footer > span { flex: none; }
.m3-hint { margin: 0; font-size: 11px; color: var(--color-muted); }
.m3-form-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 25px; padding-top: 23px; border-top: 1px solid var(--color-border); }
.m3-notice { padding: 13px 15px; border: 1px solid #e7d8bb; background: #fffbf2; color: #806332; border-radius: 8px; font-size: 12px; line-height: 1.8; margin: 0 0 22px; }
.m3-error { font-size: 13px; color: var(--color-danger); margin: 18px 0 0; }
.m3-guide { padding: 24px 22px; background: #f9fcfc; }
.m3-guide-icon { display: grid; place-items: center; width: 44px; height: 44px; color: var(--color-brand); background: var(--color-brand-soft); border-radius: 10px; margin-bottom: 19px; }
.m3-guide h3 { margin: 0 0 22px; font-size: 15px; }
.m3-guide ol { padding: 0 0 0 20px; margin: 0; color: var(--color-brand); }
.m3-guide li { padding-left: 5px; margin-bottom: 20px; font-size: 13px; }
.m3-guide strong { font-size: 13px; color: var(--color-text); font-weight: 550; }
.m3-guide li p { font-size: 12px; color: var(--color-muted); margin: 7px 0 0; line-height: 1.8; }
.m3-guide-note { font-size: 11px; color: var(--color-muted); border-top: 1px solid var(--color-border); padding-top: 18px; margin: 0; line-height: 1.9; }
.m3-no-access { display: grid; justify-items: center; gap: 14px; text-align: center; padding: 45px 20px; color: var(--color-muted); }
.m3-no-access h2, .m3-no-access p { margin: 0; }
.m3-no-access p { font-size: 13px; }
@media (max-width: 850px) { .m3-create-grid { grid-template-columns: 1fr; } .m3-guide { display: none; } }
@media (max-width: 580px) { .m3-form { padding: 20px 16px; } .m3-field input, .m3-field select, .m3-field textarea { font-size: 16px; } .m3-form-actions .ui-button--primary { flex: 1; } .m3-field-footer { gap: 10px; } }
</style>
