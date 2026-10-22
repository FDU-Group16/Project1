<script setup lang="ts">
import AppIcon from './AppIcon.vue';
defineProps<{ title: string; description: string }>();
</script>
<template>
  <section class="module-intro" aria-labelledby="page-title">
    <p class="ui-eyebrow">Campus Resource Platform</p>
    <h1 id="page-title">{{ title }}</h1>
    <p class="intro-description">{{ description }}</p>
    <div class="module-message ui-panel"><span class="module-icon"><AppIcon name="building" :size="30" /></span><div><h2>服务建设中</h2><p>这里将提供{{ title }}的相关服务。</p><slot /></div></div>
  </section>
</template>
<style scoped>
.module-intro { padding-top: 12px; }
h1 { margin: 10px 0 15px; }
.intro-description { max-width: 680px; color: var(--color-muted); margin-bottom: 32px; }
.module-message { display: flex; align-items: flex-start; gap: 22px; padding: 32px; }
.module-icon { display: grid; place-items: center; width: 64px; height: 64px; border-radius: 16px; color: var(--color-brand); background: var(--color-brand-soft); flex-shrink: 0; }
.module-message h2 { margin: 3px 0 12px; }
.module-message p { color: var(--color-muted); font-size: 14px; margin-bottom: 0; }
@media (max-width: 480px) { .module-message { flex-direction: column; padding: 24px; } }
</style>
