<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { m1Api, formatTime, type Breach } from '../api';
import { errorMessage } from '../../../shared/api/client';
import RequestState from '../../../shared/components/RequestState.vue';
const offset = ref(0); const total = ref(0);
const items = ref<Breach[]>([]); const loading = ref(false); const error = ref('');
async function load() { loading.value = true; error.value = ''; try { const result = await m1Api.breaches(offset.value); items.value = result.items; total.value = result.total; } catch (cause) { error.value = errorMessage(cause); } finally { loading.value = false; } }
onMounted(load);
function page(next: number) { offset.value = next; void load(); }
</script>
<template><div><header class="feature-header"><p class="ui-eyebrow">ATTENDANCE HISTORY</p><h1>失约记录</h1><p>查看未按时签到的预约记录，合理安排下一次自习。</p></header><RequestState :loading="loading" :error="error" :empty="!items.length" empty-text="目前没有失约记录" @retry="load" /><div v-if="!loading && !error" class="feature-list"><article v-for="item in items" :key="item.id" class="feature-panel ui-panel"><div class="feature-row"><div><h2>未按时签到</h2><p>{{ formatTime(item.occurredAt) }} · 北京时间</p></div><span class="ui-badge">失约</span></div><p class="feature-note reason">{{ item.reason }}</p><RouterLink :to="`/m1/reservations/${item.reservationId}`" class="ui-button">查看关联预约</RouterLink></article></div><div v-if="!loading && !error && total > 10" class="feature-actions" aria-label="分页"><button class="ui-button" :disabled="offset === 0" @click="page(offset - 10)">上一页</button><span>{{ Math.floor(offset / 10) + 1 }} / {{ Math.ceil(total / 10) }}</span><button class="ui-button" :disabled="offset + 10 >= total" @click="page(offset + 10)">下一页</button></div></div></template>
<style scoped src="../../../shared/styles/feature.css"></style><style scoped>.reason{margin:20px 0}</style>
