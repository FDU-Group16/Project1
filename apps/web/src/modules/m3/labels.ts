import type { Category, OrderStatus } from './types';
export const categoryLabels: Record<Category, string> = { electrical: '电气照明', plumbing: '给排水', furniture: '桌椅设施', network: '网络设备', other: '其他故障' };
export const statusLabels: Record<OrderStatus, string> = {
  REPORTED: '待派单', ASSIGNED: '已派单', STARTING_REPAIR: '下架同步中', IN_PROGRESS: '维修中',
  PENDING_ACCEPTANCE: '待验收', ACCEPTING: '恢复同步中', CLOSED: '已完成', CANCELLED: '已取消',
};
export const roleLabels = { student: '报修人', dispatcher: '物业调度', technician: '维修人员' };
export const actionLabels: Record<string, string> = {
  REPORTED: '上报故障', ASSIGN: '派单', START: '申请开始维修', COMPLETE: '提交完工',
  ACCEPT: '验收通过，等待恢复', REJECT: '退回维修', CANCEL: '取消工单', RATE: '提交评价',
  RETRY_SYNC: '重新安排同步', ESCALATED: '超时升级', SYNC_FAILED: '同步失败',
  SYNC_RETRY_SCHEDULED: '已安排同步重试', M1_ACTIVE_CONFIRMED: '座位下架已确认',
  M1_RELEASE_CONFIRMED: '本工单下架限制已解除',
};
export function displayTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return '—';
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
}
