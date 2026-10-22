<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { m1Api } from '../api';
import { errorMessage } from '../../../shared/api/client';
import RequestState from '../../../shared/components/RequestState.vue';
const maxHours = ref(4); const loading = ref(false); const saving = ref(false); const error = ref(''); const saveError = ref(''); const message = ref('');
async function load() { loading.value = true; error.value = ''; try { maxHours.value = (await m1Api.settings()).maxReservationHours; } catch (cause) { error.value = errorMessage(cause); } finally { loading.value = false; } }
async function save() { saving.value = true; message.value = ''; saveError.value = ''; try { maxHours.value = (await m1Api.updateSettings(maxHours.value)).maxReservationHours; message.value = '预约时长设置已保存。'; } catch (cause) { saveError.value = errorMessage(cause); } finally { saving.value = false; } }
onMounted(load);
</script>
<template><div><header class="feature-header"><p class="ui-eyebrow">RESERVATION SETTINGS</p><h1>预约设置</h1><p>配置个人预约时长上限，由服务端统一校验。</p></header><RequestState :loading="loading" :error="error" @retry="load" /><form v-if="!loading && !error" class="feature-panel ui-panel" @submit.prevent="save"><label class="feature-field">单次预约最长小时数<input v-model.number="maxHours" type="number" min="1" max="24" step="1" required /></label><p class="feature-note">调整影响后续预约，不修改已有预约时段。</p><p v-if="message" class="feature-success" role="status">{{ message }}</p><p v-if="saveError" class="feature-error" role="alert">{{ saveError }}</p><div class="feature-actions"><button class="ui-button ui-button--primary" :disabled="saving">{{ saving ? '正在保存…' : '保存设置' }}</button></div></form></div></template>
<style scoped src="../../../shared/styles/feature.css"></style>
