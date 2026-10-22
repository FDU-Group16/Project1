<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import PreviewNotice from '../components/PreviewNotice.vue';
import ServiceUnavailable from '../components/ServiceUnavailable.vue';
import { exampleReservations } from '../preview/fixtures';

const props = defineProps<{ preview?: boolean }>();
const route = useRoute();
const reservation = computed(() => props.preview ? exampleReservations.find((item) => item.key === route.params.id) : undefined);
const backTo = computed(() => props.preview ? { path: '/m1/preview/reservations', query: { tab: reservation.value?.category ?? 'current' } } : { path: '/m1/reservations' });
</script>

<template>
  <div class="m1-reservation-detail-page">
    <PreviewNotice v-if="preview" />
    <RouterLink class="m1-back ui-link" :to="backTo"><AppIcon name="arrow-left" :size="16" />返回{{ preview ? '预约示例' : '我的预约' }}</RouterLink>
    <header class="m1-page-heading"><p class="ui-eyebrow">RESERVATION DETAILS</p><h1>{{ preview ? '预约详情示例' : '预约详情' }}</h1><p>{{ preview ? '查看一段自习时光的安排。' : '查看预约的房间、座位与时段。' }}</p></header>
    <ServiceUnavailable v-if="!preview" identity preview-to="/m1/preview/reservations" />
    <section v-else-if="reservation" class="m1-detail-card ui-panel" aria-labelledby="m1-detail-room">
      <div class="m1-detail-top"><span class="m1-detail-icon"><AppIcon name="calendar" :size="28" /></span><span class="ui-badge">{{ reservation.status }} · 示例</span></div>
      <h2 id="m1-detail-room">{{ reservation.room }} · {{ reservation.seat }}</h2>
      <p class="m1-detail-period">{{ reservation.period }}</p>
      <p class="m1-detail-date">{{ reservation.date }} · {{ reservation.duration }} · 北京时间</p>
      <dl><div><dt>房间</dt><dd>{{ reservation.room }}</dd></div><div><dt>座位编号</dt><dd>{{ reservation.seat }}</dd></div><div><dt>座位设施</dt><dd>{{ reservation.socket ? '有插座' : '无插座' }}</dd></div><div><dt>展示状态</dt><dd>{{ reservation.status }}（固定示例）</dd></div></dl>
      <div class="m1-detail-note"><AppIcon name="info" :size="18" /><p>这是只读界面示例，未产生真实预约。正式服务接入后，将依据预约状态提供相应操作。</p></div>
    </section>
    <section v-else class="m1-missing ui-panel"><AppIcon name="calendar" :size="28" /><h2>未找到此预约示例</h2><p>这个链接没有对应的展示记录，请返回示例列表。</p><RouterLink to="/m1/preview/reservations" class="ui-button ui-button--primary">查看预约示例</RouterLink></section>
  </div>
</template>

<style scoped>
.m1-back { display: inline-flex; gap: 7px; align-items: center; font-size: 13px; margin-bottom: 22px; }
.m1-page-heading { margin-bottom: 25px; }
.m1-page-heading h1 { font-size: clamp(25px, 3vw, 32px); font-weight: 650; margin: 10px 0; letter-spacing: -.6px; }
.m1-page-heading > p:last-child { margin: 0; font-size: 14px; color: var(--color-muted); line-height: 1.8; }
.m1-detail-card { padding: 30px; max-width: 760px; }
.m1-detail-top { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
.m1-detail-icon { width: 58px; height: 58px; background: var(--color-brand-soft); color: var(--color-brand); border-radius: 15px; display: grid; place-items: center; }
.m1-detail-card h2 { font-size: 20px; font-weight: 650; margin: 22px 0 0; }
.m1-detail-period { font-size: 32px; font-weight: 550; margin: 25px 0 9px; }
.m1-detail-date { font-size: 13px; color: var(--color-muted); margin: 0; }
.m1-detail-card dl { display: grid; margin: 27px 0 0; padding: 10px 0; border-top: 1px solid var(--color-border); }
.m1-detail-card dl > div { display: grid; grid-template-columns: 100px minmax(0,1fr); gap: 20px; padding: 12px 0; font-size: 14px; }
.m1-detail-card dt { color: var(--color-muted); }
.m1-detail-card dd { margin: 0; }
.m1-detail-note { border-top: 1px solid var(--color-border); padding-top: 20px; display: flex; align-items: flex-start; gap: 10px; color: var(--color-muted); }
.m1-detail-note > svg { flex: none; margin-top: 2px; color: var(--color-brand); }
.m1-detail-note p { margin: 0; line-height: 1.8; font-size: 13px; }
.m1-missing { text-align: center; display: grid; justify-items: center; padding: 40px 20px; }
.m1-missing > svg { color: var(--color-brand); }
.m1-missing h2 { font-size: 20px; margin: 18px 0 0; }
.m1-missing p { font-size: 14px; color: var(--color-muted); margin: 12px 0 22px; line-height: 1.7; }
@media (max-width: 480px) { .m1-detail-card { padding: 20px; } .m1-detail-card dl > div { grid-template-columns: 76px minmax(0,1fr); gap: 12px; } .m1-detail-period { font-size: 28px; } }
</style>
