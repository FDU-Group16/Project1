<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import PreviewNotice from '../components/PreviewNotice.vue';
import ServiceUnavailable from '../components/ServiceUnavailable.vue';
import { exampleReservations } from '../preview/fixtures';

const props = defineProps<{ preview?: boolean }>();
const route = useRoute();
const router = useRouter();
const tab = computed(() => route.query.tab === 'history' ? 'history' : 'current');
const reservations = computed(() => props.preview ? exampleReservations.filter((item) => item.category === tab.value) : []);
function changeTab(next: string) { void router.push({ query: { tab: next } }); }
</script>

<template>
  <div class="m1-reservations-page">
    <PreviewNotice v-if="preview" />
    <header class="m1-page-heading"><p class="ui-eyebrow">MY RESERVATIONS</p><h1>{{ preview ? '预约记录示例' : '我的预约' }}</h1><p>{{ preview ? '浏览当前安排与历史记录的展示方式。' : '查看自习安排，让每一次专注都有计划。' }}</p></header>
    <div class="m1-tabs" role="group" aria-label="预约范围"><button type="button" :aria-pressed="tab === 'current'" @click="changeTab('current')">当前预约</button><button type="button" :aria-pressed="tab === 'history'" @click="changeTab('history')">历史预约</button></div>
    <template v-if="preview">
      <p class="m1-tab-summary" aria-live="polite">{{ tab === 'current' ? '当前预约示例' : '历史预约示例' }} · {{ reservations.length }} 条</p>
      <div class="m1-reservation-list">
        <article v-for="item in reservations" :key="item.key" class="m1-reservation ui-panel">
          <div class="m1-reservation-top"><div class="m1-room-title"><span><AppIcon name="building" :size="23" /></span><div><h2>{{ item.room }}</h2><p>{{ item.seat }} 号座位 · 示例记录</p></div></div><span class="ui-badge" :class="{ 'm1-history-badge': item.category === 'history' }">{{ item.status }} · 示例</span></div>
          <div class="m1-reservation-time"><p>{{ item.period }}</p><span><AppIcon name="calendar" :size="15" />{{ item.date }}<i aria-hidden="true">·</i>{{ item.duration }}</span></div>
          <div class="m1-reservation-bottom"><span><AppIcon :name="item.socket ? 'plug' : 'seat'" :size="15" />{{ item.socket ? '座位配有插座' : '普通座位，无插座' }}</span><RouterLink :to="`/m1/preview/reservations/${item.key}`" class="ui-button" :aria-label="`查看${item.room} ${item.seat}预约示例详情`">查看详情<AppIcon name="arrow-right" :size="16" /></RouterLink></div>
        </article>
      </div>
      <p class="m1-footnote"><AppIcon name="info" :size="14" />示例日期固定，用于呈现不同状态，不会随真实预约变化。</p>
    </template>
    <ServiceUnavailable v-else identity :preview-to="`/m1/preview/reservations?tab=${tab}`" />
  </div>
</template>

<style scoped>
.m1-page-heading h1 { font-size: clamp(25px, 3vw, 32px); font-weight: 650; margin: 10px 0; letter-spacing: -.6px; }
.m1-page-heading > p:last-child { margin: 0; font-size: 14px; color: var(--color-muted); line-height: 1.8; }
.m1-tabs { display: flex; gap: 28px; border-bottom: 1px solid var(--color-border); margin: 28px 0 22px; }
.m1-tabs button { appearance: none; background: transparent; padding: 12px 2px 15px; color: var(--color-muted); border: 0; border-bottom: 2px solid transparent; font: inherit; font-size: 14px; cursor: pointer; min-height: 44px; }
.m1-tabs button[aria-pressed='true'] { color: var(--color-brand); border-bottom-color: var(--color-brand); font-weight: 650; }
.m1-tab-summary { font-size: 12px; color: var(--color-muted); margin: 0 0 14px; }
.m1-reservation-list { display: grid; gap: 16px; }
.m1-reservation { padding: 26px; }
.m1-reservation-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.m1-room-title { display: flex; align-items: center; gap: 13px; }
.m1-room-title > span { display: grid; place-items: center; width: 46px; height: 46px; border-radius: 12px; background: var(--color-brand-soft); color: var(--color-brand); flex: none; }
.m1-room-title h2 { font-size: 17px; font-weight: 650; margin: 0 0 6px; }
.m1-room-title p { font-size: 12px; color: var(--color-muted); margin: 0; }
.m1-history-badge { color: var(--color-muted); background: var(--color-page); }
.m1-reservation-time { margin: 30px 0 25px; }
.m1-reservation-time p { font-size: 29px; font-weight: 550; letter-spacing: -.5px; margin: 0 0 10px; }
.m1-reservation-time > span { display: flex; gap: 8px; align-items: center; color: var(--color-muted); font-size: 13px; }
.m1-reservation-time i { font-style: normal; }
.m1-reservation-bottom { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 18px; padding-top: 20px; border-top: 1px solid var(--color-border); }
.m1-reservation-bottom > span { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--color-muted); }
.m1-footnote { display: flex; align-items: flex-start; gap: 7px; color: var(--color-muted); font-size: 12px; line-height: 1.8; margin: 20px 0 0; }
.m1-footnote > svg { flex: none; margin-top: 3px; }
@media (max-width: 480px) { .m1-reservation { padding: 20px; } .m1-reservation-time p { font-size: 27px; } }
</style>
