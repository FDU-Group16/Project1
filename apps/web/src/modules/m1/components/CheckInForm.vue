<script setup lang="ts">
import { ref } from 'vue';
import { m1Api, type Reservation } from '../api';
import { errorMessage } from '../../../shared/api/client';
const props = defineProps<{ reservation: Reservation }>();
const emit = defineEmits<{ updated: [reservation: Reservation] }>();
const code = ref(''); const busy = ref(false); const error = ref('');
async function submit() { if (busy.value) return; busy.value = true; error.value = ''; try { emit('updated', await m1Api.checkIn(props.reservation.id, code.value.trim())); code.value = ''; } catch (cause) { error.value = errorMessage(cause); } finally { busy.value = false; } }
</script>
<template><form class="feature-panel ui-panel" @submit.prevent="submit"><h2>到场签到</h2><p class="feature-note">在房间现场获取当日签到编码。请在预约开始后的 15 分钟内提交；时间与编码由服务端校验。</p><label class="feature-field">签到编码<input v-model="code" autocomplete="off" inputmode="numeric" required maxlength="16" placeholder="输入现场展示的编码" /></label><p v-if="error" class="feature-error" role="alert">{{ error }}</p><div class="feature-actions"><button class="ui-button ui-button--primary" :disabled="busy">{{ busy ? '正在签到…' : '确认签到' }}</button></div></form></template>
<style scoped src="../../../shared/styles/feature.css"></style>
