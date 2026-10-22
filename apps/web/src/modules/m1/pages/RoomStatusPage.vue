<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { hasPermission } from '../../../shared/auth';
import { errorMessage } from '../../../shared/api/client';
import RequestState from '../../../shared/components/RequestState.vue';
import { m1Api, formatTime, type Provenance } from '../api';
const offset = ref(0); const total = ref(0);
const route = useRoute(); const loading = ref(false); const error = ref(''); const items = ref<Provenance[]>([]); const code = ref<Awaited<ReturnType<typeof m1Api.code>> | null>(null); const codeError = ref('');
async function load() { loading.value = true; error.value = ''; try { const result = await m1Api.provenance(String(route.params.roomId), offset.value); items.value = result.items; total.value = result.total; } catch (cause) { error.value = errorMessage(cause); } finally { loading.value = false; } }
async function loadCode() { codeError.value = ''; code.value = null; try { code.value = await m1Api.code(String(route.params.roomId)); } catch (cause) { codeError.value = errorMessage(cause); } }
onMounted(load);
function page(next: number) { offset.value = next; void load(); }
</script>
<template><div><header class="feature-header"><p class="ui-eyebrow">ROOM STATUS PROVENANCE</p><h1>房间状态与签到编码</h1><p>房间 ID：{{ route.params.roomId }}</p></header><section v-if="hasPermission('room:manage')" class="feature-panel ui-panel"><h2>现场签到编码</h2><p class="feature-note">仅由空间管理员在房间现场展示，供本房间预约用户输入。</p><button class="ui-button" @click="loadCode">获取当日编码</button><p v-if="codeError" class="feature-error" role="alert">{{ codeError }}</p><div v-if="code" aria-live="polite"><p class="check-in-code">{{ code.code }}</p><p class="feature-note">{{ code.date }} · 有效至 {{ formatTime(code.expiresAt) }}（北京时间）</p></div></section><h2>状态来源记录</h2><p class="feature-note">这里展示 M1 保存的 M1 / M2 / M3 变更来源，不表示其他业务模块已完成集成或 D 审计已接入。</p><RequestState :loading="loading" :error="error" :empty="!items.length" empty-text="暂无来源记录" @retry="load" /><div v-if="!loading && !error" class="feature-list"><article v-for="item in items" :key="item.id" class="feature-panel ui-panel"><div class="feature-row"><h2>{{ item.sourceSystem }} · {{ item.action }}</h2><span class="feature-note">{{ formatTime(item.createdAt) }}</span></div><dl class="feature-details"><div><dt>来源编号</dt><dd>{{ item.sourceId }}</dd></div><div><dt>变更详情</dt><dd><pre>{{ JSON.stringify(item.detail, null, 2) }}</pre></dd></div></dl></article></div><div v-if="!loading && !error && total > 10" class="feature-actions" aria-label="分页"><button class="ui-button" :disabled="offset === 0" @click="page(offset - 10)">上一页</button><span>{{ Math.floor(offset / 10) + 1 }} / {{ Math.ceil(total / 10) }}</span><button class="ui-button" :disabled="offset + 10 >= total" @click="page(offset + 10)">下一页</button></div></div></template>
<style scoped src="../../../shared/styles/feature.css"></style><style scoped>.check-in-code{font-size:36px;letter-spacing:.15em;color:var(--color-brand);font-variant-numeric:tabular-nums;margin:22px 0 10px}pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}</style>
