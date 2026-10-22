<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import RequestState from '../../../shared/components/RequestState.vue';
import { errorMessage } from '../../../shared/api/client';
import { m1Api, formatTime, statusLabel, type Reservation } from '../api';
const route = useRoute(); const router = useRouter();
const scope = computed(() => route.query.tab === 'history' ? 'history' : 'current');
const offset = computed(() => Math.max(0, Number.parseInt(String(route.query.offset ?? '0'), 10) || 0));
const items = ref<Reservation[]>([]); const total = ref(0); const loading = ref(false); const error = ref(''); let sequence = 0;
async function load() { const current = ++sequence; loading.value = true; error.value = ''; items.value = []; try { const result = await m1Api.reservations(scope.value, offset.value); if (current === sequence) { items.value = result.items; total.value = result.total; } } catch (cause) { if (current === sequence) error.value = errorMessage(cause); } finally { if (current === sequence) loading.value = false; } }
watch([scope, offset], load, { immediate: true });
function page(next: number) { void router.push({ query: { tab: scope.value, offset: Math.max(0, next) } }); }
</script>
<template><div><header class="feature-header"><p class="ui-eyebrow">MY RESERVATIONS</p><h1>我的预约</h1><p>查看自习安排，让每一次专注都有计划。</p></header><div class="feature-tabs" role="group" aria-label="预约范围"><button v-for="tab in [{ key: 'current', label: '当前预约' }, { key: 'history', label: '历史预约' }]" :key="tab.key" class="ui-button" :aria-pressed="scope === tab.key" @click="router.push({ query: { tab: tab.key } })">{{ tab.label }}</button></div><RequestState :loading="loading" :error="error" :empty="!items.length" empty-text="暂无这个范围的预约" @retry="load" /><template v-if="!loading && !error"><p class="feature-note" role="status">共 {{ total }} 条记录 · 北京时间</p><div class="feature-list"><article v-for="item in items" :key="item.id" class="feature-panel ui-panel"><div class="feature-row"><div><h2>{{ item.roomName }}</h2><p>{{ item.seatNumber }} 号座位</p></div><span class="ui-badge">{{ statusLabel[item.status] }}</span></div><p class="period">{{ formatTime(item.startsAt) }} — {{ formatTime(item.endsAt) }}</p><RouterLink :to="`/m1/reservations/${item.id}`" class="ui-button">查看详情与操作</RouterLink></article></div><div v-if="total > 10" class="feature-actions" aria-label="分页"><button class="ui-button" :disabled="offset === 0" @click="page(offset - 10)">上一页</button><span>{{ Math.floor(offset / 10) + 1 }} / {{ Math.ceil(total / 10) }}</span><button class="ui-button" :disabled="offset + 10 >= total" @click="page(offset + 10)">下一页</button></div></template></div></template>
<style scoped src="../../../shared/styles/feature.css"></style><style scoped>.period{font-size:22px;font-weight:550;margin:26px 0;overflow-wrap:anywhere}@media(max-width:480px){.period{font-size:18px}}</style>
