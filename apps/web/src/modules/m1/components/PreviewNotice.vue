<script setup lang="ts">
import AppIcon from '../../../shared/components/AppIcon.vue';
</script>

<template>
  <aside class="m1-preview-note" aria-label="示例数据说明">
    <AppIcon name="info" :size="20" />
    <div><strong>示例数据，非实时可约信息</strong><p>仅用于浏览界面，不能提交预约、取消或签到；以下记录不属于真实用户。</p></div>
    <RouterLink class="ui-link" to="/m1">返回正式入口<AppIcon name="arrow-right" :size="16" /></RouterLink>
  </aside>
</template>

<style scoped>
.m1-preview-note { display: flex; align-items: flex-start; gap: 12px; padding: 16px 18px; border: 1px solid #c1ddd5; border-radius: var(--radius, 12px); background: var(--color-brand-soft); color: var(--color-brand); margin-bottom: 26px; }
.m1-preview-note > svg { flex: none; margin-top: 2px; }
.m1-preview-note strong { font-size: 14px; }
.m1-preview-note p { margin: 5px 0 0; font-size: 13px; line-height: 1.65; }
.m1-preview-note > a { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-size: 13px; }
@media (max-width: 640px) { .m1-preview-note { display: grid; grid-template-columns: 20px minmax(0, 1fr); } .m1-preview-note > div { min-width: 0; } .m1-preview-note > a { grid-column: 2; margin-left: 0; justify-self: start; } }
</style>
