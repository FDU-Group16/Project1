<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <section aria-labelledby="page-title">
    <p class="eyebrow">Campus Resource Platform</p>
    <h1 id="page-title">{{ title }}</h1>
    <p>{{ description }}</p>
    <slot />
  </section>
</template>

<style scoped>
section {
  line-height: 1.7;
}

.eyebrow {
  color: #166b76;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 12px 0 20px;
  font-size: clamp(2rem, 5vw, 3.4rem);
}
</style>
