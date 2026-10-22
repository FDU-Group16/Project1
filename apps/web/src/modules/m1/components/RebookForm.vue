<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { m1Api, idempotencyKey } from '../api';
import { errorMessage } from '../../../shared/api/client';
import { beijingDate, filterInterval, validateFilters, startHours, endHours, hourLabel } from '../search';
const props = defineProps<{ reservationId: string }>();
const router = useRouter(); const maxHours = ref(4); const date = ref(beijingDate()); const start = ref('18'); const end = ref('20'); const busy = ref(false); const error = ref('');
let payload = ''; let key = idempotencyKey();
onMounted(async () => { try { maxHours.value = (await m1Api.settings()).maxReservationHours; } catch { /* Reservation endpoint remains authoritative. */ } });
async function submit() {
  if (busy.value) return;
  const filters = { date: date.value, start: start.value, end: end.value, socket: false }; const validation = validateFilters(filters, maxHours.value); error.value = validation.date ?? validation.time ?? ''; if (error.value) return;
  const times = filterInterval(filters); const current = JSON.stringify(times); if (payload !== current) { payload = current; key = idempotencyKey(); }
  busy.value = true;
  try { const reservation = await m1Api.rebook(props.reservationId, times.startsAt, times.endsAt, key); await router.push(`/m1/reservations/${reservation.id}`); }
  catch (cause) { error.value = `${errorMessage(cause)} 重试同一时段不会重复创建预约。`; }
  finally { busy.value = false; }
}
</script>
<template><form class="feature-panel ui-panel" @submit.prevent="submit"><h2>再次预约这个座位</h2><p class="feature-note">重新选择日期与时段，系统会再次检查院系权限、开放时间与实时占用。</p><fieldset :disabled="busy"><div class="feature-grid"><label class="feature-field">日期<input v-model="date" type="date" :min="beijingDate()" required /></label><label class="feature-field">开始<select v-model="start"><option v-for="hour in startHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></label><label class="feature-field">结束<select v-model="end"><option v-for="hour in endHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></label></div></fieldset><p v-if="error" class="feature-error" role="alert">{{ error }}</p><div class="feature-actions"><button class="ui-button ui-button--primary" :disabled="busy">{{ busy ? '正在预约…' : '再次预约' }}</button></div></form></template>
<style scoped src="../../../shared/styles/feature.css"></style><style scoped>fieldset{border:0;padding:0;margin:0;min-width:0}</style>
