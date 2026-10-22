<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppIcon from '../../../shared/components/AppIcon.vue';
import RequestState from '../../../shared/components/RequestState.vue';
import { hasPermission } from '../../../shared/auth';
import { errorMessage } from '../../../shared/api/client';
import { m1Api, idempotencyKey, type Seat } from '../api';
import { beijingDate, filtersFromQuery, filtersToQuery, validateFilters, filterInterval, startHours, endHours, hourLabel } from '../search';
const route = useRoute(); const router = useRouter();
const filters = ref(filtersFromQuery(route.query)); const maxHours = ref(4); const settingsError = ref('');
const loading = ref(false); const searched = ref(false); const error = ref(''); const formError = ref(''); const seats = ref<Seat[]>([]);
const selected = ref<Seat | null>(null); const reserving = ref(false); const reservationError = ref(''); const requestKey = ref(idempotencyKey());
let sequence = 0;
const rooms = computed(() => [...new Set(seats.value.map(seat => seat.roomId))].map(id => ({ id, name: seats.value.find(seat => seat.roomId === id)?.roomName, seats: seats.value.filter(seat => seat.roomId === id) })));
function resetResults() { sequence++; loading.value = false; seats.value = []; selected.value = null; searched.value = false; error.value = ''; reservationError.value = ''; requestKey.value = idempotencyKey(); }
watch(filters, resetResults, { deep: true });
watch(() => route.query, () => { const next = filtersFromQuery(route.query); if (JSON.stringify(next) !== JSON.stringify(filters.value)) filters.value = next; });
async function loadSettings() { try { maxHours.value = (await m1Api.settings()).maxReservationHours; settingsError.value = ''; } catch (cause) { settingsError.value = errorMessage(cause); } }
onMounted(loadSettings);
async function search() {
  const errors = validateFilters(filters.value, maxHours.value); formError.value = errors.date ?? errors.time ?? '';
  if (formError.value) return;
  selected.value = null; reservationError.value = ''; requestKey.value = idempotencyKey();
  await router.replace({ query: filtersToQuery(filters.value) });
  const current = ++sequence; loading.value = true; searched.value = true; error.value = ''; seats.value = [];
  try { const times = filterInterval(filters.value); const result = await m1Api.seats(times.startsAt, times.endsAt, filters.value.socket); if (current === sequence) seats.value = result.items; }
  catch (cause) { if (current === sequence) error.value = errorMessage(cause); }
  finally { if (current === sequence) loading.value = false; }
}
function select(seat: Seat) { selected.value = seat; reservationError.value = ''; requestKey.value = idempotencyKey(); }
async function reserve() {
  if (!selected.value || reserving.value) return;
  reserving.value = true; reservationError.value = '';
  try { const result = await m1Api.reserve({ seatId: selected.value.id, roomId: selected.value.roomId, ...filterInterval(filters.value) }, requestKey.value); await router.push(`/m1/reservations/${result.id}`); }
  catch (cause) { reservationError.value = `${errorMessage(cause)} 如结果不确定，可再次提交同一选择以安全重试，或前往“我的预约”确认。`; }
  finally { reserving.value = false; }
}
</script>
<template>
  <div><header class="feature-header"><p class="ui-eyebrow">SEAT RESERVATION</p><h1>给专注留一个位置</h1><p>选择自习时段，查找对你开放的房间与座位。</p></header>
    <form class="feature-panel ui-panel" @submit.prevent="search"><fieldset :disabled="reserving" class="filter-fieldset"><div class="feature-grid"><label class="feature-field">预约日期<input v-model="filters.date" type="date" :min="beijingDate()" required /></label><label class="feature-field">开始时间<select v-model="filters.start"><option v-for="hour in startHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></label><label class="feature-field">结束时间<select v-model="filters.end"><option v-for="hour in endHours" :key="hour" :value="hour">{{ hourLabel(hour) }}</option></select></label></div><div class="feature-actions"><label class="feature-check"><input v-model="filters.socket" type="checkbox" />仅看带插座的座位</label><button class="ui-button ui-button--primary" :disabled="loading"><AppIcon name="search" :size="16" />{{ loading ? '正在查询…' : '查询座位' }}</button></div></fieldset><p v-if="formError" class="feature-error" role="alert">{{ formError }}</p></form>
    <p class="feature-note">北京时间 · 按整点小时预约 · 单次最长 {{ maxHours }} 小时 · 开始前可以取消</p><p v-if="settingsError" class="feature-error" role="status">预约设置加载失败：{{ settingsError }} 当前显示 4 小时参考值，最终以服务端校验为准。</p>
    <RequestState :loading="loading" :error="error" :empty="searched && !seats.length && !loading && !error" empty-text="这个时段暂无可预约座位" @retry="search" />
    <section v-if="!searched" class="feature-panel ui-panel"><h2>从选择时间开始</h2><p class="feature-note">查询结果依据你的院系、开放时间、现有预约、整室占用和维修状态实时筛选。</p></section>
    <div v-if="!loading && !error" class="feature-list"><section v-for="room in rooms" :key="room.id" class="feature-panel ui-panel"><div class="feature-row"><div><h2>{{ room.name }}</h2><p>{{ room.seats.length }} 个可预约座位</p></div><AppIcon name="building" :size="25" /></div><div class="seat-grid"><button v-for="seat in room.seats" :key="seat.id" type="button" :disabled="reserving" class="seat" :class="{ selected: selected?.id === seat.id }" :aria-pressed="selected?.id === seat.id" :aria-label="`${room.name} ${seat.number}号座位，${seat.hasSocket ? '有插座' : '无插座'}`" @click="select(seat)"><AppIcon name="seat" :size="22" /><strong>{{ seat.number }}</strong><span>{{ seat.hasSocket ? '有插座' : '无插座' }}</span></button></div></section></div>
    <section v-if="selected" class="feature-panel ui-panel selection" aria-live="polite"><h2>确认这段专注时光</h2><p>{{ selected.roomName }} · {{ selected.number }} 号座位</p><p class="feature-note">{{ filters.date }} {{ hourLabel(filters.start) }}–{{ hourLabel(filters.end) }} · 北京时间</p><p v-if="reservationError" class="feature-error" role="alert">{{ reservationError }}</p><div class="feature-actions"><button class="ui-button ui-button--primary" :disabled="reserving || !hasPermission('seat:reserve')" @click="reserve">{{ reserving ? '正在预约…' : '确认预约' }}</button><button class="ui-button" :disabled="reserving" @click="selected = null">重新选择</button></div><p v-if="!hasPermission('seat:reserve')" class="feature-error">当前身份没有个人预约权限。</p></section>
  </div>
</template>
<style scoped src="../../../shared/styles/feature.css"></style>
<style scoped>.filter-fieldset{border:0;margin:0;padding:0;min-width:0}.seat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:12px;margin-top:24px}.seat{display:flex;flex-direction:column;align-items:center;gap:6px;min-height:106px;border:1px solid #c4dadd;border-radius:9px;background:#f5faf9;color:var(--color-brand);padding:12px}.seat span{font-size:11px;color:var(--color-muted)}.seat.selected{border:2px solid var(--color-brand);background:var(--color-brand-soft)}.selection{border-color:#8db8bd}.selection h2{font-size:18px}</style>
