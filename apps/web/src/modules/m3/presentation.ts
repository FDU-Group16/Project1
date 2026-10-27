import type { Category, OrderAction, OrderStatus, Role } from './api';

export const statusLabels: Record<OrderStatus, string> = {
  SUBMITTED: '待派单', ASSIGNED: '待开工', BLOCK_PENDING: '等待下架', IN_PROGRESS: '维修中',
  PENDING_ACCEPTANCE: '待验收', RELEASE_PENDING: '等待恢复', CLOSED: '已完成', CANCELLED: '已取消',
};
export const categoryLabels: Record<Category, string> = { facilities: '设施损坏', electrical: '电器与用电', environment: '环境问题', other: '其他故障' };
export const roleLabels: Record<Role, string> = { reporter: '报修人', admin: '管理员', technician: '维修人员' };
export const actionLabels: Record<OrderAction, string> = {
  assign: '派单', start: '开始维修', complete: '提交完工', accept: '验收通过', reject: '退回返工', cancel: '取消工单', rate: '提交评价', 'retry-sync': '重试同步',
};
const historyLabels: Record<string, string> = {
  ...actionLabels, create: '提交报修', created: '提交报修', escalate: '超时升级', escalated: '超时升级',
  block_applied: '房间下架已确认', release_applied: '本工单限制已解除', sync_succeeded: '同步成功', sync_failed: '同步失败',
  submitted: '提交报修', 'block-confirmed': '房间下架已确认', 'release-confirmed': '本工单限制已解除',
  'sync-failed': '同步失败', 'sla-escalated': '超时升级',
};
export const historyLabel = (action: string) => historyLabels[action] ?? action;
export function formatTime(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '—' : new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
}
export const shortId = (id: string) => id.length > 12 ? id.slice(-8).toUpperCase() : id.toUpperCase();
