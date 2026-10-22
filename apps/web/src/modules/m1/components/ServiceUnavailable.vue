<script setup lang="ts">
import AppIcon from '../../../shared/components/AppIcon.vue';

defineProps<{ identity?: boolean; previewTo: string }>();
</script>

<template>
  <section class="m1-service ui-panel" aria-labelledby="m1-service-title">
    <span class="m1-service-icon"><AppIcon :name="identity ? 'shield' : 'search'" :size="27" /></span>
    <h2 id="m1-service-title">{{ identity ? '身份服务尚未接入' : '座位查询服务尚未接入' }}</h2>
    <p>{{ identity ? '接入统一身份后，你可以在这里查看自己的预约与历史记录。' : '你可以先选择自习时段。接入服务后，这里将显示对你开放的房间与实时座位信息。' }}</p>
    <RouterLink :to="previewTo" class="ui-button ui-button--primary">浏览界面示例<AppIcon name="arrow-right" :size="16" /></RouterLink>
    <small>示例浏览无需登录，不会产生预约。</small>
  </section>
</template>

<style scoped>
.m1-service { display: grid; justify-items: center; text-align: center; padding: 42px 24px; gap: 14px; }
.m1-service-icon { display: grid; place-items: center; width: 64px; height: 64px; background: var(--color-brand-soft); color: var(--color-brand); border-radius: 20px; margin-bottom: 5px; }
.m1-service h2 { margin: 0; font-size: 19px; font-weight: 650; }
.m1-service p { max-width: 480px; margin: 0 0 5px; color: var(--color-muted); line-height: 1.8; }
.m1-service small { color: var(--color-muted); font-size: 12px; }
</style>
