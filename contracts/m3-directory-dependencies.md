# M3 目录消费提案 0.1.0

状态：**proposed / consumer implemented**。2026-10-27 的 M3 适配任务范围已经确认；本文件不是 M2/D-01 已实现或团队已完成接口评审的声明。与 [D 公共依赖 0.1.0](d-dependencies.md)、[D-02 主数据 0.1.0](d-master-data.md) 一起评审。提供方状态仍以 `services/d/PROVIDES.json` 为准。

## 用户身份与权限

M3 对每个需鉴权的请求，通过真实 HTTP `GET {M3_IDENTITY_BASE_URL}/api/v1/auth/me` 验证浏览器共享会话的 `Authorization: Bearer <user-token>`。不从浏览器的角色、用户 ID、部门或代理头授权，不缓存已撤销的会话，不把令牌写入工单、历史或日志。

成功 200：`{id,displayName,departmentId,permissions}`。`id` 为非空字符串且不超过 128 字；`displayName` 为非空字符串且不超过 200 字；`departmentId` 必填、为 null 或非空字符串；`permissions` 必须为字符串数组。可附加其他字段。现有 `seat:reserve` 兼容为报修资格；新增以下权限是待 D-01 负责人评审的消费假设：

| 权限 | M3 权限 |
| --- | --- |
| `repair:report` 或 `seat:reserve` | 创建报修；对象本人可验收、取消及关闭后一次评价 |
| `repair:dispatch` | 全模块工单管理、派单、重派、代验、重试同步；代验仍须理由，实际维修参与者仍不能自验 |
| `repair:work` | 对本人当前受派的工单开工和完工 |

权限可以组合。`GET /api/m3/v1/me` 的 `role` 为 UI 展示用主角色，优先级 admin (`repair:dispatch`) > technician (`repair:work`) > reporter；业务操作仍使用完整可信权限集合，不因主角色覆盖其他权限。`room:manage`、`operations:read` 均不授予 M3 权限。只有 dispatch/work 而没有 report/seat:reserve 的身份不能新建报修。M3 目前不解释尚未定义的维修管理范围字段；`repair:dispatch` 在该提案中是全模块管理权，不能由房间管理权推导。

## 维修人员目录（待提供方实现）

`GET {M3_IDENTITY_BASE_URL}/api/v1/repair-technicians`，携带当前维修管理员的用户 Bearer，仅 `repair:dispatch` 可访问。成功 200 返回 `{items:[{id,displayName,permissions}]}`；可附带 `departmentId`，省略时按 null 处理。每项必须含 `repair:work`，ID 不重复，其他字段约束与身份相同。目录不暴露其他用户的令牌。M3 对外转换为 `{items:[{id,name,role:"technician"}]}`，派单时重新查询当前目录；下一次维修操作独立鉴权，不把目录返回当作永久授权。

该 endpoint 当前没有正式 D-01 实现。测试中的独立 HTTP 身份夹具和显式开发身份只验证消费方，不能将此提案登记为可用提供方。

## D-02 房间与 M1 凭据

`GET {D_BASE_URL}/api/v1/rooms` 携带当前用户的 Bearer，使用已实现的 D-02 公共接口。D-02 执行院系与用户可见范围；M3 只接受列表内 `active=true && retired=false` 的房间，转换为 `{id,name}`。创建工单重新取目录，不信任用户提交的房间名称、院系或前端选项。查询某些既有工单或处理已受派工单无需再次访问 D-02，避免房间目录临时故障阻止查看已存工单。

**不使用 `D_M1_TOKEN`**，不调用 M1 专用内部目录，不直接访问 D 表。M3→M1 使用独立的 `M3_M1_TOKEN`；提供方配置 `M1_M3_TOKEN` 为同一秘密，并与 M2 凭据区分。遵循 `m1-room-blocks.openapi.json@0.2.0-proposed`，不改变请求和回执形状。

## 失败、装配与兼容

目录 401 → M3 401；目录 403 → M3 403；连接、超时、重定向、其他非 200（含尚不存在的接口 404）及无效 JSON/字段 → M3 503。失败不能变为合成成功。响应限制 1 MiB，列表最多 5000 项，不接受重复 ID；拒绝将用户凭据跟随 HTTP 重定向转发。

正式装配要求 `M3_MODE=production`、`M3_DIRECTORY_MODE=http`、有效 `M3_IDENTITY_BASE_URL`/`D_BASE_URL`、独立 PostgreSQL `M3_DATABASE_URL`、真实 `M3_M1_BASE_URL`/`M3_M1_TOKEN`。未配置完整时仅健康与上下文可用。`context.businessReady` 只表示本地装配已启用，**不表示远端 D-01 已就绪或健康**；真实请求仍严格验证远端结果。`M3_DIRECTORY_TIMEOUT_SECONDS` 默认 3 秒。

用户令牌不授予 M1 内部服务权限；M1 服务令牌不会进入浏览器。正式数据库必须与演示数据库分离；已有开发来源或未标注依赖来源的旧工单会阻止生产 worker 启动，须人工评审迁移，不能自动改标签后发送。
