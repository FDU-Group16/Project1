<script setup lang="ts">
import { RouterView } from 'vue-router';
import AppLayout from './shared/layouts/AppLayout.vue';

const navigation = [
  { label: '首页', to: '/' },
  { label: '座位预约', to: '/m1' },
  { label: '整室申请', to: '/m2' },
  { label: '报修工单', to: '/m3' },
];
</script>

<template>
  <AppLayout :navigation="navigation">
    <RouterView />
  </AppLayout>
</template>
