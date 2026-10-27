<script setup lang="ts">
import { statusLabels } from '../labels';
import type { OrderStatus } from '../types';
defineProps<{ status: OrderStatus }>();
</script>
<template><span class="m3-status" :class="`m3-status--${status.toLowerCase()}`"><span aria-hidden="true"></span>{{ statusLabels[status] ?? status }}</span></template>
<style scoped>
.m3-status { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; border-radius: 5px; font-size: 12px; line-height: 1.5; padding: 5px 9px; color: #63747b; background: #f0f4f5; }
.m3-status > span { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.m3-status--reported, .m3-status--pending_acceptance { color: #8a591d; background: #fff3df; }
.m3-status--in_progress, .m3-status--assigned { color: #176d78; background: #e9f3f4; }
.m3-status--starting_repair, .m3-status--accepting { color: #60538a; background: #f0edf8; }
.m3-status--closed { color: #307655; background: #eaf5ee; }
</style>
