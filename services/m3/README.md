# M3 物业报修工单

本轮在本地工作区实现 M3 业务：故障上报、权限与可见范围、派单/重派、维修、完工、验收/返工、评价、取消、SLA 升级、持久化与 M1 写回 outbox。正式 D 身份/房间目录和 M1 提供方尚未接通；默认运行拒绝业务请求，不会自动切换为演示身份。

## 运行本地开发演示

在仓库根目录安装依赖并启动 M3：

```bash
uv sync --frozen
bash services/m3/run-dev.sh
```

脚本显式开启 `development`、合成身份/房间和 `M3_M1_MODE=stub`，仅监听 `127.0.0.1:3103`。数据库在忽略版本控制的 `services/m3/.local/work-orders.sqlite3`，重启后保留。演示 M1 仅产生契约回执，**不会修改真实座位**。第二个终端启动现有 Vue：

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

访问 `http://localhost:5173/m3`，界面显式选择开发身份。演示顺序：同学一上报 → 调度员派给维修员一 → 维修员一开始维修并提交完工 → 同学一验收并评价。详情页同步状态表示本次依赖模式的回执，不是上线证据。API 文档在 `http://127.0.0.1:3103/docs`。

| 开发 token | 服务端身份 | 角色 |
| --- | --- | --- |
| `demo-student` | `student-1` | 学生/上报者 |
| `demo-student-2` | `student-2` | 另一位学生（不可读他人工单） |
| `demo-dispatcher` | `dispatcher-1` | 物业调度 |
| `demo-technician` | `technician-1` | 维修员一 |
| `demo-technician-2` | `technician-2` | 维修员二 |

以上是公开合成夹具，不是真实凭据，不可用于正式认证。清单在 `dev_dependencies.py`，每次载入是相同的目录，幂等且不写业务工单。首次数据库为空；不向真实 D 表写种子，也不替 D 建主数据。

## 数据库与迁移

`database.py` 管理 M3 专属 SQLAlchemy Core 存储；`migrations/v0001.py` 建立工单、创建幂等键、写回 outbox、事务锁以及版本校验。PostgreSQL 的逻辑 schema 为 `m3`，SQLite 仅映射到本地 main。迁移记录校验源文件 SHA256，重复运行不重建或清空数据；修改已应用版本会被拒绝。

显式运行开发迁移：

```bash
M3_MODE=development \
M3_DATABASE_URL=sqlite:///services/m3/.local/work-orders.sqlite3 \
uv run python -m services.m3.migrate
```

先运行启动脚本或 `mkdir -p services/m3/.local` 建目录。开发启动自动运行同一迁移器；正式发布必须先运行迁移命令，使用由部署维护者提供的 **M3 独立账号**：

```bash
# 由安全环境提供 M3_DATABASE_URL，不把数据库密码写入代码或提交。
M3_MODE=production uv run python -m services.m3.migrate
```

PostgreSQL URL 使用 `postgresql+psycopg://...` 或 `postgresql://...`。正式身份适配器尚未实现，因此 production 仍拒绝业务请求且不启动 worker；配置数据库不代表正式业务就绪。当前迁移没有删除回退；正式部署前需备份和兼容性审核，不能通过改迁移或手工改库修复版本。全组迁移/独立账号/流水线部署仍待集成。

本轮为课程规模采用 M3 内串行写事务（PostgreSQL 锁专有 guard 行，SQLite BEGIN IMMEDIATE），简化并发状态一致性。网络调用在事务外，跨进程 worker 使用数据库 lease 防重复落地。此方案限制写吞吐；列表与 SLA 扫描当前遍历本模块工单，规模扩大需索引化查询、分页与队列调优。

## M1 真实接口接入

既有契约为 `contracts/m1-room-blocks.openapi.json@0.1.0-proposed`。有可用提供方后，可在保留开发 D 身份的集成环境显式启用真实 HTTP：

```bash
# M3_M1_URL / M3_M1_TOKEN 由环境安全提供；该命令不会回退到 stub。
M3_M1_MODE=http bash services/m3/run-dev.sh
```

每张工单以自己的 ID 为 sourceId，开始维修 ACTIVE revision 1，验收 RELEASED revision 2。重试不增 revision，严格核对来源、房间、版本、完整时段、目标状态和 UTC 回执时间。HTTP 200 但回执错仍失败；不跟随重定向，以免转发凭据。

网络异常及 502/503/504 最多自动尝试 5 次（5/10/20/40 秒退避，封顶 60 秒）；进程重启恢复到期 lease，仍使用原请求。失败始终保留 STARTING_REPAIR/ACCEPTING，不能提前宣称联动成功。暂时错误耗尽后，调度者确认依赖修复，可用带 `version` 与 `reason` 的 `retry-sync` 重试同一请求。

401/403/404/409/422、错误回执和配置错误不会自动重试，须 M3/M1/D 相关组核对身份、房间、来源和已落地状态，形成恢复任务；本轮没有绕过永久错误的恢复按钮。**不得手工改数据库、变更 revision 或伪造回执绕过冲突。** M1 多工单及 M1/M2 限制保留必须在真实提供方验收；本模块测试只证明独立来源请求，没有证明 M1 座位行为。

## SLA、审计与待接入通知

派单 SLA 默认上报后 24 小时；维修 SLA 默认首次派单后 48 小时，覆盖等待开始及维修中。重派不推迟截止时间；验收拒绝后开始新的 48 小时返工阶段。边界 `now >= dueAt` 即升级，每阶段一次；升级标记不会替代维修状态或撤销座位阻断。完工待验收不自动关闭、不默认通过。

配置项 `M3_ASSIGNMENT_SLA_HOURS`、`M3_REPAIR_SLA_HOURS` 控制 SLA；`M3_WORKER_INTERVAL_SECONDS` 默认 2 秒。历史记录与业务变更在同事务持久化，不是 D 共享审计服务。升级记录清楚标明 D 通知尚未接入，不能将它当作通知送达。

## 验证

```bash
uv run python -m unittest discover -s services/m3/tests -v
bash scripts/check.sh
```

测试覆盖状态机、越权、防枚举、严格输入、幂等/并发、重启恢复、SLA 精确边界、M1 网络回执及 Uvicorn 真实 HTTP 全流程。开发依赖为显式替身，业务逻辑未被 mock。可选 PostgreSQL 测试需专用可丢弃测试数据库：

```bash
# 环境安全提供 M3_TEST_POSTGRES_URL，绝不使用生产数据库。
uv run python -m unittest services.m3.tests.test_postgres -v
```

没有该变量会明确跳过；本机 PostgreSQL 尚未验证。需求、临时依赖清理与实际证据见 [任务方案](docs/2026-10-26-implementation.md)、[状态记录](STATUS.md)。
