# M3 工单 API 与依赖约定 v0.1.0-proposed

2026-10-26。M3 自有接口开发基线；待 M3 组评审，不代表全组通过或已部署。实现生成的 OpenAPI 将保存于同目录 `m3-work-orders.openapi.json`，与本记录共同评审。字段使用 camelCase，UTC 时间以 Z 结尾，拒绝未声明请求字段。全部路径前缀 `/api/m3/v1`。

## 身份与运行模式

`GET /context` 无需身份，返回 `{mode, dependencyMode, message}`。mode 为 unconfigured/development/production；dependencyMode 为 unavailable/stub/http。没有 D 身份适配器的正常运行必须拒绝业务请求，不能接受浏览器传入的 userId/roles。开发身份仅在显式 development 模式接受固定演示 Bearer token：demo-student、demo-student-2、demo-dispatcher、demo-technician、demo-technician-2。它们分别映射 user ID student-1、student-2、dispatcher-1、technician-1、technician-2；是公开合成夹具，非真实凭据，禁止正式部署使用。

业务请求使用 `Authorization: Bearer ...`。`GET /me` 返回 `{id, name, roles}`，roles 为 student/dispatcher/technician 数组。`GET /rooms` 返回 `{items:[{id,name}]}`；`GET /technicians` 仅调度人员可访问，返回 `{items:[{id,name}]}`。

## 工单入口

- `POST /work-orders`：头 `Idempotency-Key` 必填；体 `{roomId,title,description,category}`，category 为 electrical/plumbing/furniture/network/other。同操作者同键同内容返回同一对象；不同内容 409。
- `GET /work-orders`：返回 `{items: WorkOrder[]}`，按当前身份可见性过滤，最新在前。
- `GET /work-orders/{id}`：返回 WorkOrder，无权访问与不存在均 404。
- `POST /work-orders/{id}/assign`：`{version,assigneeId}`，仅 dispatcher。
- `POST /work-orders/{id}/start`：`{version}`，仅当前 technician。
- `POST /work-orders/{id}/complete`：`{version,resolution}`，仅当前 technician。
- `POST /work-orders/{id}/accept`：`{version}`，仅 reporter。
- `POST /work-orders/{id}/reject`：`{version,reason}`，仅 reporter。
- `POST /work-orders/{id}/cancel`：`{version,reason}`，仅 reporter，限 REPORTED/ASSIGNED。
- `POST /work-orders/{id}/rate`：`{version,rating,comment}`，rating 为 1～5 整数，仅 reporter，限 CLOSED，一次。
- `POST /work-orders/{id}/retry-sync`：`{version,reason}`，仅 dispatcher，限临时失败重试耗尽后的人工恢复；沿用原来源版本和完整请求。永久错误不允许盲目重试。
- 以上操作返回最新 WorkOrder；旧 version、错误状态、重复评价等 409。身份缺失/无效 401，角色动作越权 403，输入不合法 422，依赖不可用 503。

WorkOrder 字段：`id,roomId,roomName,title,description,category,reporterId,assigneeId|null,status,version,createdAt,updatedAt,dueAt|null,escalated:boolean,rating:number|null,comment|null,resolution|null,syncStatus`（NONE/PENDING/SYNCED/FAILED），`syncError:string|null,history:[{action,actorId,at,detail}]`。公开错误使用 `{code,detail}`；校验错误可为 FastAPI 标准 422 detail。动作不会信任客户端时间或操作者。

## 状态、一致性与 SLA

状态转换、角色、默认 SLA 和待评审事项见 [M3 任务方案](../services/m3/docs/2026-10-26-implementation.md)。STARTING_REPAIR 等待 M1 ACTIVE 回执，ACCEPTING 等待 RELEASED 回执；业务成功和网络同步成功必须区分。

M1 请求严格遵循 `m1-room-blocks.openapi.json@0.1.0-proposed`，不修改对方契约。每工单独立稳定来源键、递增 revision、持久化完整请求，重试不增版本。同步回执匹配来源/房间/版本/状态/时间后才提交对应业务转换。M3 只撤销自己的来源。超时升级本地记录不等于 D 通知送达。

## 兼容与评审

现有 M1/M2/D 接口保持不变。M3 前端由 M3 组维护，公共 Web/部署组评审 `/api/m3/` 转发，D 组评审身份/目录接入，M1 组评审写回的失败恢复和多来源集成。正式数据库采用 PostgreSQL；SQLite 限显式本地开发/测试。未经实际验证，不能把本地工作区标为已发布或真实集成完成。
