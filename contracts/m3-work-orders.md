# M3 工单接口 v1（本轮实现基线）

2026-10-27：本任务用户已确认的 M3 业务方案，现已迁到 `develop@13dcd59` 独立副本适配。跨组契约、D 集成和 schema 仍须相关负责人在合入 develop 前评审；不是团队已批准或已上线的声明。M1 写回消费 `0.2.0-proposed`，保持其请求与回执形状。

## HTTP 与对象

基础路径 `/api/m3/v1`；JSON 字段 camelCase；时间 UTC RFC3339 Z；Bearer 身份。除 `/context` 外均需身份。Web 使用共享登录；M3 通过 D-01 HTTP 逐请求验证身份，再以同一用户令牌访问 D-02 房间目录。权限与拟议维修人员接口见 [目录消费提案 0.1.0](m3-directory-dependencies.md)。D-01 仍未提供正式实现；远端失败拒绝业务，不回退演示身份。

- `GET /context` → `{mode, directoryMode, m1Mode, businessReady, demoIdentities: [{id,name,role,token}]}`。仅显式 development/test 且启用开发目录时返回合成身份；正式模式列表为空。`businessReady` 只表示本地业务装配，不能替代远端依赖健康和联调证据。
- `GET /me` → `{id,name,role}`，role 为 reporter/admin/technician，取可信权限的展示优先级 dispatch > work > report；多权限操作用完整权限集合校验，不能仅根据前端 role 授权。
- `GET /rooms` → `{items:[{id,name}]}`；`GET /technicians` → `{items:[{id,name,role}]}`，维修人员目录仅管理员可查。
- `GET /work-orders?status=&roomId=&view=&q=` → `{items: WorkOrder[]}`，view 为 all/mine/assigned/acceptance/overdue，先执行对象权限过滤再筛选。
- `POST /work-orders`：需要 `repair:report` 或 `seat:reserve`；`Idempotency-Key` 必填，长度 1–128，去除首尾空白后须为非空可打印 ASCII；请求 `{roomId,category,title,description}`；category 为 facilities/electrical/environment/other。标题 1–120 字、描述 1–4000 字（去除首尾空白后）；成功 201，幂等回放 200。
- `GET /work-orders/{id}` → `WorkOrder`。
- `POST /work-orders/{id}/{action}`：所有动作必填整数 `version>=1`，成功返回最新 `WorkOrder`。动作参数见下。

`WorkOrder`：`{id,roomId,roomName,category,title,description,reporterId,reporterName,assigneeId,assigneeName,status,version,createdAt,updatedAt,dueAt,escalated,rating,sync,history,allowedActions}`。
`rating` 为 null 或 `{score,comment,createdAt}`；`sync` 为 null 或 `{status,attempts,error,retryable}`，status 为 pending/processing/succeeded/failed；`history` 为 `[{id,action,actorId,actorName,note,createdAt}]`；`allowedActions` 为当前用户可执行的动作字符串列表。无受派人/时限时相应字段为 null。

错误统一 `{error:{code,message}}`；401 无身份、403 无权限、404 不存在或不可见、409 版本/状态/幂等冲突、422 无效参数、503 外部依赖未就绪。不返回异常堆栈/令牌。

## 动作、权限及状态

状态：SUBMITTED → ASSIGNED → BLOCK_PENDING → IN_PROGRESS → PENDING_ACCEPTANCE → RELEASE_PENDING → CLOSED；开始维修前可 CANCELLED。

- assign：管理员，SUBMITTED/ASSIGNED/IN_PROGRESS，`assigneeId` 必填。重派不重置截止时间，旧维修员即时撤权。
- start：当前维修人员，ASSIGNED；创建 ACTIVE 版本 1 outbox，进入 BLOCK_PENDING；有效 M1 回执后 IN_PROGRESS。
- complete：当前维修人员，IN_PROGRESS，`note` 必填；进入 PENDING_ACCEPTANCE，停止 SLA，保留房间 ACTIVE。
- accept：原报修人或管理员，PENDING_ACCEPTANCE；管理员代验 `note` 必填。历次实际维修参与者均不得验收。创建 RELEASED 版本 2，进入 RELEASE_PENDING；有效回执后 CLOSED。
- reject：与 accept 同权限，`note` 必填；返回 IN_PROGRESS，保持 ACTIVE，重新开始 48 小时 SLA。
- cancel：原报修人或管理员，SUBMITTED/ASSIGNED，`note` 必填。
- rate：原报修人，CLOSED，仅一次；`score` 为整数 1–5，`comment` 可选最长 2000 字。
- retry-sync：管理员，仅暂时错误重试耗尽，沿用原来源/版本/完整载荷。

一般 note 最长 2000 字；未知字段拒绝。SLA：创建起 24h 未派单、首次派单起 48h 未完工（包括等待下架），`now>=dueAt` 每阶段只升级一次并记入管理员待办和历史；重派不延长；返工为新阶段。

## M1 与恢复

工单变化、历史、幂等及 outbox 同事务写入；网络请求不放在数据库事务内。worker 使用持久租约。HTTP 适配使用现有 M1 契约、服务 Bearer、稳定关联 ID；校验完整回执、UTC时间及 appliedAt。网络异常/502/503/504最多自动尝试5次（1/5/30/120秒退避），其他错误停止。重启后恢复租约，连续崩溃仍计入尝试预算。

同房间每张工单拥有独立来源；释放仅释放本工单，不操作 M1/M2 的表或内部代码。真实提供方未就绪时，仅消费者替身测试可通过，真实联调单独记录。
