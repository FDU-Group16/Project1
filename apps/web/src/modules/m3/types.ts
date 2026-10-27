export type Role = 'student' | 'dispatcher' | 'technician';
export type Category = 'electrical' | 'plumbing' | 'furniture' | 'network' | 'other';
export type OrderStatus = 'REPORTED' | 'ASSIGNED' | 'STARTING_REPAIR' | 'IN_PROGRESS' | 'PENDING_ACCEPTANCE' | 'ACCEPTING' | 'CLOSED' | 'CANCELLED';
export interface ServiceContext {
  mode: 'unconfigured' | 'development' | 'production';
  dependencyMode: 'unavailable' | 'stub' | 'http';
  message: string;
}
export interface Actor { id: string; name: string; roles: Role[] }
export interface DirectoryItem { id: string; name: string }
export interface NewOrder { roomId: string; title: string; description: string; category: Category }
export interface WorkOrder {
  id: string;
  roomId: string;
  roomName: string;
  title: string;
  description: string;
  category: Category;
  reporterId: string;
  assigneeId: string | null;
  status: OrderStatus;
  version: number;
  createdAt: string;
  updatedAt: string;
  dueAt: string | null;
  escalated: boolean;
  rating: number | null;
  comment: string | null;
  resolution: string | null;
  syncStatus: 'NONE' | 'PENDING' | 'SYNCED' | 'FAILED';
  syncError: string | null;
  history: { action: string; actorId: string; at: string; detail: string }[];
}
export type OrderAction = 'assign' | 'start' | 'complete' | 'accept' | 'reject' | 'cancel' | 'rate' | 'retry-sync';
export interface PendingCreate { key: string; payload: NewOrder; uncertain: boolean }
