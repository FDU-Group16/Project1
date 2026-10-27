<script setup lang="ts">
import type { OrderStatus } from '../api';
import { statusLabels } from '../presentation';
defineProps<{ status: OrderStatus }>();
</script>
<template><span class="status-badge" :class="status.toLowerCase()"><span aria-hidden="true"></span>{{ statusLabels[status] }}</span></template>
<style scoped>
.status-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 9px; border-radius:6px; background:#edf2f3; color:#53666d; font-size:12px; font-weight:550; white-space:nowrap; }
.status-badge > span { width:5px; height:5px; border-radius:50%; background:currentColor; }
.submitted,.pending_acceptance { color:#805a1d; background:#fcf2df; }
.assigned { color:#3d5f8f; background:#edf2fb; }
.in_progress { color:#166b76; background:#e5f3f3; }
.block_pending,.release_pending { color:#76578c; background:#f3edf7; }
.closed { color:#34724e; background:#edf6ef; }
</style>
