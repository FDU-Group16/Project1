<script setup lang="ts">
import { useRoute } from 'vue-router';
import { auth } from '../auth';
defineProps<{ loading?: boolean; error?: string; empty?: boolean; emptyText?: string }>();
defineEmits<{ retry: [] }>();
const route = useRoute();
</script>
<template>
  <div v-if="loading" class="request-state ui-panel" role="status">正在加载，请稍候…</div>
  <div v-else-if="error" class="request-state ui-panel" role="alert"><h2>暂时无法完成操作</h2><p>{{ error }}</p><RouterLink v-if="!auth.session" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="ui-button ui-button--primary">前往登录</RouterLink><button v-else class="ui-button" type="button" @click="$emit('retry')">重试</button></div>
  <div v-else-if="empty" class="request-state ui-panel" role="status"><h2>{{ emptyText || '暂无记录' }}</h2><p>可调整条件后重新查询。</p></div>
</template>
<style scoped>.request-state{padding:30px;text-align:center;color:var(--color-muted);margin:18px 0}.request-state h2{font-size:18px}.request-state p{overflow-wrap:anywhere}</style>
