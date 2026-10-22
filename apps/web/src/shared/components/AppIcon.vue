<script setup lang="ts">
import { computed } from 'vue';
const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 });
const icons: Record<string, string[]> = {
  seat: ['M6 11V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6', 'M4 10v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5', 'M6 17v4m12-4v4M4 13h16'],
  calendar: ['M8 2v4m8-4v4M3 10h18', 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z', 'M7 14h2m6 0h2m-10 4h2'],
  grid: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  'arrow-right': ['M4 12h16m-6-6 6 6-6 6'],
  'arrow-left': ['M20 12H4m6-6-6 6 6 6'],
  'chevron-right': ['m9 5 7 7-7 7'],
  'chevron-down': ['m5 9 7 7 7-7'],
  menu: ['M4 6h16M4 12h16M4 18h16'],
  x: ['m6 6 12 12M6 18 18 6'],
  user: ['M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z', 'M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2'],
  info: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z', 'M12 11v6m0-10v.01'],
  search: ['M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z', 'm15 15 6 6'],
  plug: ['M8 2v5m8-5v5M6 7h12v4a6 6 0 0 1-12 0V7Zm6 10v5'],
  check: ['m5 12 4 4L19 6'],
  clock: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z', 'M12 6v6l4 2'],
  building: ['M4 22V4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v18M2 22h20', 'M8 6h1m6 0h1M8 10h1m6 0h1M8 14h1m6 0h1m-6 8v-4h4v4'],
  shield: ['M12 22s9-4 9-11V5l-9-3-9 3v6c0 7 9 11 9 11Z', 'm8 12 3 3 5-6'],
  book: ['M12 5C9 2 4 2 2 3v17c3-1 7-1 10 2 3-3 7-3 10-2V3c-2-1-7-1-10 2Zm0 0v17'],
  wrench: ['M14.6 6.4a5 5 0 0 0-6.2 6.2l-6 6a2 2 0 0 0 3 3l6-6a5 5 0 0 0 6.2-6.2l-3 3-3-3 3-3Z'],
  location: ['M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z', 'M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
  sun: ['M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z', 'M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5'],
  leaf: ['M20 3c-8-1-16 3-16 10a7 7 0 0 0 7 7c7 0 10-9 9-17Z', 'M3 22 15 10'],
};
const paths = computed(() => icons[props.name] ?? icons.info);
</script>
<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" class="app-icon">
    <path v-for="(path, index) in paths" :key="index" :d="path" />
  </svg>
</template>
<style scoped>
.app-icon { flex-shrink: 0; vertical-align: middle; }
</style>
