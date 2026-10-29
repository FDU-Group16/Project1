<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { prepareDraft, type ApplicationDraft, type DraftErrors, type DraftInput } from '../draft';

const fields = reactive<DraftInput>({ roomId: '', startLocal: '', endLocal: '', purpose: '', attendeeCount: '' });
const errors = ref<DraftErrors>({});
const preview = ref<ApplicationDraft | null>(null);
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

watch(fields, () => { preview.value = null; errors.value = {}; });

function showPreview() {
  const result = prepareDraft(fields);
  errors.value = result.errors;
  preview.value = result.draft;
  if (result.errors.roomId) document.getElementById('m2-room')?.focus();
  else if (result.errors.startLocal) document.getElementById('m2-start')?.focus();
  else if (result.errors.endLocal) document.getElementById('m2-end')?.focus();
  else if (result.errors.purpose) document.getElementById('m2-purpose')?.focus();
  else if (result.errors.attendeeCount) document.getElementById('m2-count')?.focus();
}

function resetDraft() {
  fields.roomId = '';
  fields.startLocal = '';
  fields.endLocal = '';
  fields.purpose = '';
  fields.attendeeCount = '';
  errors.value = {};
  preview.value = null;
  document.getElementById('m2-room')?.focus();
}
</script>

<template>
  <div class="m2-draft">
    <RouterLink to="/m2" class="ui-link">← 返回整室申请</RouterLink>
    <header>
      <p class="ui-eyebrow">M2 · 本地草稿</p>
      <h1>准备整室申请</h1>
      <p>填写后可核对申请内容。此页面不会保存或发送数据，也不会创建申请。</p>
    </header>
    <form class="ui-panel m2-form" novalidate aria-label="整室申请草稿" @submit.prevent="showPreview">
      <div class="m2-grid">
        <div class="m2-field">
          <label for="m2-room">房间 ID</label>
          <input id="m2-room" v-model="fields.roomId" autocomplete="off" required :aria-invalid="Boolean(errors.roomId)" :aria-describedby="errors.roomId ? 'm2-room-error' : undefined" />
          <small>使用房间目录提供的 ID；此处不验证房间是否可用。</small>
          <p v-if="errors.roomId" id="m2-room-error" class="m2-error" role="alert">{{ errors.roomId }}</p>
        </div>
        <div class="m2-field">
          <label for="m2-count">预计人数</label>
          <input id="m2-count" v-model="fields.attendeeCount" type="number" inputmode="numeric" min="1" step="1" required :aria-invalid="Boolean(errors.attendeeCount)" :aria-describedby="errors.attendeeCount ? 'm2-count-error' : undefined" />
          <p v-if="errors.attendeeCount" id="m2-count-error" class="m2-error" role="alert">{{ errors.attendeeCount }}</p>
        </div>
        <div class="m2-field">
          <label for="m2-start">开始时间</label>
          <input id="m2-start" v-model="fields.startLocal" type="datetime-local" required :aria-invalid="Boolean(errors.startLocal)" :aria-describedby="errors.startLocal ? 'm2-start-error' : undefined" />
          <p v-if="errors.startLocal" id="m2-start-error" class="m2-error" role="alert">{{ errors.startLocal }}</p>
        </div>
        <div class="m2-field">
          <label for="m2-end">结束时间</label>
          <input id="m2-end" v-model="fields.endLocal" type="datetime-local" required :aria-invalid="Boolean(errors.endLocal)" :aria-describedby="errors.endLocal ? 'm2-end-error' : undefined" />
          <p v-if="errors.endLocal" id="m2-end-error" class="m2-error" role="alert">{{ errors.endLocal }}</p>
        </div>
        <div class="m2-field m2-wide">
          <label for="m2-purpose">用途</label>
          <textarea id="m2-purpose" v-model="fields.purpose" rows="4" maxlength="500" required :aria-invalid="Boolean(errors.purpose)" :aria-describedby="errors.purpose ? 'm2-purpose-error' : undefined" />
          <p v-if="errors.purpose" id="m2-purpose-error" class="m2-error" role="alert">{{ errors.purpose }}</p>
        </div>
      </div>
      <p class="m2-hint">输入时间按你设备的 {{ timeZone }} 时区解释；预览中的时间会转换为 UTC。房间资格、容量和审批权限须由未来服务端验证。</p>
      <div class="m2-actions">
        <button type="submit" class="ui-button ui-button--primary">检查并预览</button>
        <button type="button" class="ui-button" @click="resetDraft">清空草稿</button>
      </div>
    </form>
    <section v-if="preview" class="ui-panel m2-preview" aria-live="polite">
      <p class="ui-eyebrow">仅本地预览 · 未提交</p>
      <h2>请核对申请内容</h2>
      <dl>
        <div><dt>房间 ID</dt><dd>{{ preview.room_id }}</dd></div>
        <div><dt>时间（UTC）</dt><dd>{{ preview.start_at }} — {{ preview.end_at }}</dd></div>
        <div><dt>预计人数</dt><dd>{{ preview.attendee_count }}</dd></div>
        <div><dt>用途</dt><dd>{{ preview.purpose }}</dd></div>
      </dl>
      <p>当前 M2 尚未提供公开申请接口。本次检查未进行身份、资格、容量或冲突校验。</p>
    </section>
  </div>
</template>

<style scoped>
.m2-draft { max-width: 850px; margin: 0 auto; padding: 8px 0 36px; }
.m2-draft header { margin: 24px 0; }
.m2-draft header p:last-child, .m2-hint, .m2-preview > p:last-child { color: var(--color-muted); line-height: 1.8; }
.m2-form, .m2-preview { padding: 24px; }
.m2-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.m2-field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.m2-wide { grid-column: 1 / -1; }
.m2-field label { font-weight: 600; }
.m2-field input, .m2-field textarea { width: 100%; min-height: 44px; padding: 9px 12px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); }
.m2-field [aria-invalid='true'] { border-color: var(--color-danger); }
.m2-field small, .m2-error { font-size: 13px; }
.m2-field small { color: var(--color-muted); }
.m2-error { color: var(--color-danger); margin: 0; }
.m2-hint { font-size: 13px; margin: 22px 0; }
.m2-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.m2-preview { margin-top: 22px; }
.m2-preview dl { display: grid; gap: 10px; }
.m2-preview dl > div { display: grid; grid-template-columns: 130px 1fr; gap: 12px; }
.m2-preview dt { color: var(--color-muted); }
.m2-preview dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 600px) { .m2-form, .m2-preview { padding: 18px; } .m2-grid { grid-template-columns: 1fr; } .m2-wide { grid-column: auto; } .m2-preview dl > div { grid-template-columns: 1fr; gap: 2px; } }
</style>
