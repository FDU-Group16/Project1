<script setup lang="ts">
import { computed } from 'vue';
import { RouterView, useRoute } from 'vue-router';
import AppLayout from './shared/layouts/AppLayout.vue';

const navigation = [
  { label: '首页', to: '/', icon: 'grid' },
  { label: '座位预约', to: '/m1', icon: 'seat' },
  { label: '整室申请', to: '/m2', icon: 'building' },
  { label: '报修工单', to: '/m3', icon: 'shield' },
];
const route = useRoute();
const isM1 = computed(() => route.meta.section === 'm1');
const preview = computed(() => route.meta.preview === true);
const sidebar = computed(() => {
  if (!isM1.value) return [];
  const base = preview.value ? '/m1/preview' : '/m1';
  return [
    { label: '座位搜索', to: base, icon: 'search' },
    { label: '我的预约', to: `${base}/reservations`, icon: 'calendar' },
  ];
});
</script>

<template>
  <AppLayout
    :navigation="navigation"
    :sidebar="sidebar"
    :section-title="isM1 ? '座位预约' : undefined"
    :section-description="isM1 ? '为每一段专注，找到合适的位置。' : undefined"
    :compact="route.name === 'login'"
    :preview="preview"
  >
    <RouterView />
  </AppLayout>
</template>
