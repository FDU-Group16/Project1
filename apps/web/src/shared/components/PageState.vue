<script setup lang="ts">
import AppIcon from './AppIcon.vue';
defineProps<{ code: string; title: string; description: string; icon: string }>();
</script>
<template>
  <section class="page-state ui-panel" aria-labelledby="state-title">
    <span class="state-icon"><AppIcon :name="icon" :size="32" /></span>
    <p class="ui-eyebrow">{{ code }}</p><h1 id="state-title">{{ title }}</h1><p class="state-description">{{ description }}</p><div class="state-actions"><slot /></div>
  </section>
</template>
<style scoped>
.page-state { max-width: 680px; margin: 48px auto; padding: 58px 32px; text-align: center; }
.state-icon { display: grid; place-items: center; margin: 0 auto 25px; width: 72px; height: 72px; border-radius: 21px; color: var(--color-brand); background: var(--color-brand-soft); }
.ui-eyebrow { margin-bottom: 14px; }
h1 { font-size: 26px; margin-bottom: 16px; }
.state-description { color: var(--color-muted); font-size: 13px; max-width: 420px; margin: 0 auto 26px; }
.state-actions { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 12px; }
@media (max-width: 480px) { .page-state { margin: 24px auto; padding: 36px 22px; } h1 { font-size: 23px; } }
</style>
