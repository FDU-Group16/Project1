<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { dApi, weekdays, type Room } from '../api';
import { errorMessage } from '../../../shared/api/client';
import RequestState from '../../../shared/components/RequestState.vue';
const rooms = ref<Room[]>([]); const loading = ref(false); const error = ref('');
async function load() { loading.value = true; error.value = ''; try { rooms.value = (await dApi.rooms()).items; } catch (cause) { error.value = errorMessage(cause); } finally { loading.value = false; } }
onMounted(load);
const daysLabel = (days: number[]) => days.map(day => weekdays[day]).join('、');
</script>
<template><div><header class="feature-header"><p class="ui-eyebrow">SPACE DIRECTORY</p><h1>房间与座位管理</h1><p>维护开放范围、开放时段与座位基础信息。</p><RouterLink to="/d/rooms/new" class="ui-button ui-button--primary">登记新房间</RouterLink></header><RequestState :loading="loading" :error="error" :empty="!rooms.length" empty-text="尚未登记房间" @retry="load" /><div v-if="!loading && !error" class="feature-list"><article v-for="room in rooms" :key="room.id" class="feature-panel ui-panel"><div class="feature-row"><div><h2>{{ room.name }}</h2><p>{{ room.departmentId ? `所属院系：${room.departmentId}` : '公共空间 · 向所有院系开放' }}</p></div><span class="ui-badge">{{ room.retired ? '已注销' : room.active ? '开放使用' : '已停用' }}</span></div><p class="feature-note hours">{{ String(room.openHour).padStart(2, '0') }}:00–{{ String(room.closeHour).padStart(2, '0') }}:00 · {{ daysLabel(room.weekdays) }} · 北京时间</p><RouterLink :to="`/d/rooms/${room.id}`" class="ui-button">查看与管理座位</RouterLink></article></div></div></template>
<style scoped src="../../../shared/styles/feature.css"></style><style scoped>.hours{margin:22px 0}</style>
