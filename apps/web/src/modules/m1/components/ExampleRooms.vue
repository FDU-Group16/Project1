<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import AppIcon from '../../../shared/components/AppIcon.vue';
import { exampleRooms, type ExampleRoom, type ExampleSeat } from '../preview/fixtures';
import { hourLabel, type SearchFilters } from '../search';

const props = defineProps<{ filters: SearchFilters }>();
const selectedRoom = ref<ExampleRoom | null>(null);
const selectedSeat = ref<ExampleSeat | null>(null);
const detailHeading = ref<HTMLElement | null>(null);
const roomButtons = new Map<string, HTMLButtonElement>();
const availableSeats = (room: ExampleRoom) => room.seats.filter((seat) => seat.state === 'available' && (!props.filters.socket || seat.socket));
const rooms = computed(() => exampleRooms.filter((room) => Number(props.filters.start) >= room.opens && Number(props.filters.end) <= room.closes && availableSeats(room).length > 0));
const visibleSeats = computed(() => selectedRoom.value?.seats.filter((seat) => !props.filters.socket || seat.socket) ?? []);
const period = computed(() => `${props.filters.date} · ${hourLabel(props.filters.start)}–${hourLabel(props.filters.end)}`);

async function openRoom(room: ExampleRoom) {
  selectedRoom.value = room;
  selectedSeat.value = null;
  await nextTick();
  detailHeading.value?.focus();
}
function closeRoom() {
  const key = selectedRoom.value?.key;
  selectedRoom.value = null;
  selectedSeat.value = null;
  if (key) roomButtons.get(key)?.focus();
}
const seatState = (seat: ExampleSeat) => seat.state === 'occupied' ? '示例占用' : seat.state === 'unavailable' ? '示例停用' : '可选示例';
</script>

<template>
  <div class="m1-result-head"><h2 aria-live="polite">房间示例 <span>{{ rooms.length }}</span></h2><p>{{ period }} <span>北京时间</span></p></div>
  <div v-if="rooms.length" class="m1-rooms">
    <article v-for="room in rooms" :key="room.key" class="m1-room ui-panel" :class="{ 'm1-room--selected': selectedRoom?.key === room.key }">
      <div class="m1-room-symbol"><AppIcon name="building" :size="25" /></div>
      <div class="m1-room-copy"><h3>{{ room.name }}</h3><div class="m1-room-meta"><span><AppIcon name="clock" :size="14" />{{ hourLabel(room.opens) }}–{{ hourLabel(room.closes) }}</span><span>{{ room.scope }}</span></div><p class="m1-room-count"><span class="m1-dot"></span>{{ availableSeats(room).length }} 个可选座位示例</p></div>
      <div class="m1-room-action"><span v-if="room.seats.some((seat) => seat.socket)" class="m1-socket"><AppIcon name="plug" :size="13" />含插座座位</span><span v-else class="m1-no-socket">无插座座位</span><button :ref="(element) => { if (element) roomButtons.set(room.key, element as HTMLButtonElement); }" type="button" class="ui-button" :aria-expanded="selectedRoom?.key === room.key" aria-controls="m1-seat-detail" @click="openRoom(room)">查看座位<AppIcon name="arrow-right" :size="16" /></button></div>
    </article>
  </div>
  <section v-else class="m1-empty ui-panel" aria-labelledby="m1-no-results"><AppIcon name="search" :size="28" /><h3 id="m1-no-results">没有匹配的房间示例</h3><p>试着调整时段或关闭插座筛选。示例开放时段为 08:00–22:00 或 09:00–22:00。</p></section>
  <section v-if="selectedRoom" id="m1-seat-detail" class="m1-detail ui-panel" aria-labelledby="m1-room-title">
    <div class="m1-detail-head"><div><p class="ui-eyebrow">座位示例</p><h2 id="m1-room-title" ref="detailHeading" tabindex="-1">{{ selectedRoom.name }}</h2></div><button type="button" class="ui-button" @click="closeRoom">收起<AppIcon name="x" :size="15" /></button></div>
    <p class="m1-detail-caption">按编号排列，用于查看座位属性，不代表实际房间平面图。</p>
    <div class="m1-legend"><span><i class="m1-legend-available"></i>可选示例</span><span><i class="m1-legend-selected"></i>已选</span><span><i class="m1-legend-disabled"></i>占用 / 停用</span><span><AppIcon name="plug" :size="14" />配有插座</span></div>
    <div class="m1-seat-grid"><button v-for="seat in visibleSeats" :key="seat.label" type="button" class="m1-seat" :disabled="seat.state !== 'available'" :aria-pressed="selectedSeat?.label === seat.label" :aria-label="`${seat.label}，${seat.socket ? '有插座' : '无插座'}，${seatState(seat)}`" @click="selectedSeat = seat"><AppIcon name="seat" :size="22" /><span>{{ seat.label }}</span><span class="m1-seat-status"><AppIcon v-if="seat.socket" name="plug" :size="12" />{{ seat.state === 'available' ? (seat.socket ? '有插座' : '无插座') : seat.state === 'occupied' ? '占用' : '停用' }}</span></button></div>
    <div class="m1-seat-summary" aria-live="polite"><template v-if="selectedSeat"><AppIcon name="check" :size="20" /><div><strong>已选择 {{ selectedSeat.label }} · {{ selectedSeat.socket ? '有插座' : '无插座' }}</strong><p>仅查看座位属性，未创建预约。</p></div></template><template v-else><AppIcon name="info" :size="19" /><p>选择一个座位示例，查看它的属性。</p></template></div>
  </section>
</template>

<style scoped>
.m1-result-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px 20px; flex-wrap: wrap; margin: 26px 0 14px; }
.m1-result-head h2 { margin: 0; font-size: 17px; font-weight: 650; }
.m1-result-head h2 > span { display: inline-grid; place-items: center; min-width: 24px; height: 24px; margin-left: 6px; color: var(--color-brand); background: var(--color-brand-soft); border-radius: 6px; font-size: 13px; }
.m1-result-head p { margin: 0; color: var(--color-muted); font-size: 12px; }
.m1-result-head p > span { margin-left: 6px; }
.m1-rooms { display: grid; gap: 13px; }
.m1-room { padding: 22px; display: grid; grid-template-columns: 50px minmax(0, 1fr) auto; align-items: center; gap: 16px; transition: border-color .15s; }
.m1-room--selected { border-color: var(--color-brand); }
.m1-room-symbol { width: 50px; height: 50px; border-radius: 13px; background: var(--color-brand-soft); color: var(--color-brand); display: grid; place-items: center; }
.m1-room h3 { margin: 0; font-size: 17px; font-weight: 650; }
.m1-room-meta { display: flex; gap: 6px 16px; flex-wrap: wrap; margin-top: 9px; color: var(--color-muted); font-size: 12px; }
.m1-room-meta > span { display: inline-flex; align-items: center; gap: 5px; }
.m1-room-count { display: flex; align-items: center; gap: 6px; margin: 10px 0 0; color: var(--color-brand); font-size: 13px; font-weight: 550; }
.m1-dot { width: 6px; height: 6px; background: currentColor; border-radius: 50%; }
.m1-room-action { display: grid; justify-items: end; gap: 12px; }
.m1-socket { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; padding: 3px 7px; background: var(--color-brand-soft); color: var(--color-brand); border-radius: 4px; }
.m1-no-socket { color: var(--color-muted); font-size: 12px; }
.m1-detail { margin-top: 20px; padding: 24px; }
.m1-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.m1-detail h2 { margin: 5px 0 0; font-size: 20px; }
.m1-detail-caption { margin: 15px 0; font-size: 13px; color: var(--color-muted); line-height: 1.7; }
.m1-legend { display: flex; gap: 10px 18px; flex-wrap: wrap; color: var(--color-muted); font-size: 12px; }
.m1-legend > span { display: inline-flex; align-items: center; gap: 6px; }
.m1-legend i { width: 10px; height: 10px; border: 1px solid var(--color-border); border-radius: 2px; }
.m1-legend-selected { background: var(--color-brand); border-color: var(--color-brand) !important; }
.m1-legend-disabled { background: var(--color-page); }
.m1-seat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(76px, 1fr)); gap: 10px; margin: 22px 0; max-width: 720px; }
.m1-seat { display: grid; justify-items: center; gap: 5px; border: 1px solid var(--color-border); border-radius: 9px; padding: 12px 6px; background: var(--color-surface); color: var(--color-text); font: inherit; font-size: 12px; cursor: pointer; }
.m1-seat > svg { color: var(--color-muted); }
.m1-seat[aria-pressed='true'] { background: var(--color-brand-soft); border-color: var(--color-brand); color: var(--color-brand); }
.m1-seat[aria-pressed='true'] > svg { color: var(--color-brand); }
.m1-seat:disabled { cursor: not-allowed; color: var(--color-muted); background: var(--color-page); opacity: .65; }
.m1-seat-status { display: inline-flex; gap: 2px; align-items: center; font-size: 10px; }
.m1-seat-summary { display: flex; align-items: center; gap: 10px; border-top: 1px solid var(--color-border); padding-top: 18px; color: var(--color-brand); min-height: 60px; }
.m1-seat-summary p { font-size: 12px; color: var(--color-muted); margin: 4px 0 0; }
.m1-seat-summary strong { font-size: 14px; }
.m1-seat-summary > svg { flex: none; }
.m1-empty { display: grid; justify-items: center; text-align: center; padding: 40px 20px; color: var(--color-muted); }
.m1-empty > svg { color: var(--color-brand); }
.m1-empty h3 { color: var(--color-text); margin: 16px 0 6px; font-size: 17px; }
.m1-empty p { margin: 0; font-size: 13px; line-height: 1.8; max-width: 440px; }
@media (max-width: 680px) { .m1-room { grid-template-columns: 42px minmax(0,1fr); padding: 18px; gap: 12px; } .m1-room-symbol { width: 42px; height: 42px; } .m1-room-action { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; margin-top: 6px; } .m1-detail { padding: 18px; } }
@media (max-width: 380px) { .m1-room { grid-template-columns: minmax(0,1fr); } .m1-room-symbol { display: none; } .m1-room-action { flex-wrap: wrap; gap: 12px; } .m1-seat-grid { grid-template-columns: repeat(3, minmax(0,1fr)); gap: 7px; } }
</style>
