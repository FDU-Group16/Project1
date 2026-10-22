<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import ExampleRooms from '../components/ExampleRooms.vue';
import PreviewNotice from '../components/PreviewNotice.vue';
import ServiceUnavailable from '../components/ServiceUnavailable.vue';
import { beijingDate, endHours, filtersFromQuery, filtersToQuery, hourLabel, startHours, validateFilters, type SearchFilters } from '../search';

const props = defineProps<{ preview?: boolean }>();
const route = useRoute();
const router = useRouter();
const attempted = ref(false);
const dateInput = ref<HTMLInputElement | null>(null);
const startInput = ref<HTMLSelectElement | null>(null);
const filters = computed(() => filtersFromQuery(route.query));
const validation = computed(() => validateFilters(filters.value));
const errors = computed(() => attempted.value || !valid.value ? validation.value : {});
const valid = computed(() => !validation.value.date && !validation.value.time);
const hasResults = computed(() => props.preview && route.query.searched !== '0' && valid.value);
const resultKey = computed(() => JSON.stringify(filters.value));
const previewTo = computed(() => `/m1/preview?${new URLSearchParams(filtersToQuery(filters.value)).toString()}`);
watch(() => route.fullPath, () => { attempted.value = false; });

function updateFilter(key: keyof SearchFilters, value: string | boolean) {
  const updated = { ...filters.value, [key]: value } as SearchFilters;
  void router.replace({ query: { ...filtersToQuery(updated), searched: '0' } });
}
async function search() {
  attempted.value = true;
  if (!valid.value) {
    await nextTick();
    if (validation.value.date) dateInput.value?.focus();
    else startInput.value?.focus();
    return;
  }
  await router.push({ query: { ...filtersToQuery(filters.value), searched: '1' } });
  attempted.value = true;
}
</script>

<template>
  <div class="m1-search-page">
    <PreviewNotice v-if="preview" />
    <header class="m1-page-heading"><p class="ui-eyebrow">SEAT RESERVATION</p><h1>给专注留一个位置</h1><p>选择自习时段，{{ preview ? '探索房间与座位的界面示例。' : '查找对你开放的房间与座位。' }}</p></header>
    <form class="m1-filter ui-panel" novalidate aria-label="座位查询条件" @submit.prevent="search">
      <div class="m1-fields">
        <div class="m1-field m1-date"><label for="m1-date">预约日期</label><input id="m1-date" ref="dateInput" type="date" :value="filters.date" :min="beijingDate()" required :aria-invalid="Boolean(errors.date)" :aria-describedby="errors.date ? 'm1-date-error' : undefined" @change="updateFilter('date', ($event.target as HTMLInputElement).value)" /><p v-if="errors.date" id="m1-date-error" class="m1-error" role="alert">{{ errors.date }}</p></div>
        <div class="m1-field"><label for="m1-start">开始时间</label><select id="m1-start" ref="startInput" :value="filters.start" :aria-invalid="Boolean(errors.time)" :aria-describedby="errors.time ? 'm1-time-error' : undefined" @change="updateFilter('start', ($event.target as HTMLSelectElement).value)"><option v-if="!startHours.includes(filters.start)" :value="filters.start" disabled>请选择</option><option v-for="hour in startHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></div>
        <div class="m1-field"><label for="m1-end">结束时间</label><select id="m1-end" :value="filters.end" :aria-invalid="Boolean(errors.time)" :aria-describedby="errors.time ? 'm1-time-error' : undefined" @change="updateFilter('end', ($event.target as HTMLSelectElement).value)"><option v-if="!endHours.includes(filters.end)" :value="filters.end" disabled>请选择</option><option v-for="hour in endHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></div>
      </div>
      <p v-if="errors.time" id="m1-time-error" class="m1-error" role="alert">{{ errors.time }}</p>
      <div class="m1-filter-bottom"><label class="m1-checkbox"><input type="checkbox" :checked="filters.socket" @change="updateFilter('socket', ($event.target as HTMLInputElement).checked)" /><AppIcon name="plug" :size="15" />仅看带插座的座位</label><button type="submit" class="ui-button ui-button--primary"><AppIcon name="search" :size="17" />{{ preview ? '筛选示例' : '查询座位' }}</button></div>
    </form>
    <p class="m1-rules"><AppIcon name="info" :size="14" />按整点小时选择 · 单次最多 4 小时 · 北京时间</p>
    <template v-if="preview"><ExampleRooms v-if="hasResults" :key="resultKey" :filters="filters" /><section v-else class="m1-pending ui-panel" aria-live="polite"><AppIcon name="search" :size="27" /><h2>{{ valid ? '按新的条件查看示例' : '请先调整查询条件' }}</h2><p>{{ valid ? '筛选条件已更新，请点击“筛选示例”重新查看。' : '修正上方提示后，即可继续浏览房间示例。' }}</p></section></template>
    <template v-else><p v-if="attempted && valid" class="m1-query-status" role="status">查询条件已检查；座位服务尚未接入，暂时无法获取实时结果。</p><ServiceUnavailable :preview-to="previewTo" /></template>
  </div>
</template>

<style scoped>
.m1-page-heading { margin-bottom: 26px; }
.m1-page-heading h1 { font-size: clamp(25px, 3vw, 32px); font-weight: 650; margin: 10px 0 10px; letter-spacing: -.6px; }
.m1-page-heading > p:last-child { margin: 0; font-size: 14px; color: var(--color-muted); line-height: 1.8; }
.m1-filter { padding: 24px; }
.m1-fields { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 20px; }
.m1-field { display: flex; flex-direction: column; gap: 9px; min-width: 0; }
.m1-field > label { font-size: 13px; font-weight: 550; }
.m1-field input, .m1-field select { display: block; min-width: 0; width: 100%; height: 44px; border: 1px solid var(--color-border); border-radius: 7px; background: var(--color-surface); padding: 9px 12px; color: var(--color-text); font: inherit; font-size: 14px; }
.m1-field [aria-invalid='true'] { border-color: var(--color-danger); }
.m1-filter-bottom { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 18px; margin-top: 24px; border-top: 1px solid var(--color-border); padding-top: 20px; }
.m1-checkbox { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; min-height: 40px; cursor: pointer; }
.m1-checkbox > input { width: 16px; height: 16px; accent-color: var(--color-brand); margin: 0; }
.m1-checkbox > svg { color: var(--color-muted); }
.m1-error { color: var(--color-danger); font-size: 13px; margin: 5px 0 0; line-height: 1.6; }
.m1-rules { display: flex; align-items: center; gap: 6px; color: var(--color-muted); font-size: 12px; margin: 12px 0 26px; line-height: 1.8; }
.m1-rules > svg { flex: none; }
.m1-query-status { color: var(--color-brand); font-size: 13px; margin: 0 0 18px; line-height: 1.8; }
.m1-pending { display: grid; justify-items: center; text-align: center; padding: 42px 20px; color: var(--color-muted); }
.m1-pending > svg { color: var(--color-brand); }
.m1-pending h2 { margin: 16px 0 6px; font-size: 18px; color: var(--color-text); }
.m1-pending p { margin: 0; font-size: 13px; line-height: 1.8; }
@media (max-width: 680px) { .m1-filter { padding: 20px; } .m1-fields { grid-template-columns: 1fr 1fr; gap: 16px; } .m1-date { grid-column: 1/-1; } .m1-field input, .m1-field select { font-size: 16px; } }
@media (max-width: 380px) { .m1-filter { padding: 16px; } .m1-fields { grid-template-columns: minmax(0,1fr); } .m1-filter-bottom > button { width: 100%; } .m1-field input, .m1-field select { font-size: 16px; } }
</style>
