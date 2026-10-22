# D 模块状态与交接

更新时间：2026-10-22。当前 `m1` 工作树实现 D-02；不代表已人工评审、合入 develop 或部署。D 整体分工 ADR 仍是 Proposed。用户本轮明确仅完成 M1 负责的 D-02，其余 D 能力作为外部依赖。

## 已实现

| 需求 | 当前行为与入口 |
| --- | --- |
| D-02 房间 | [master_data.py](master_data.py)：登记、按范围查询、部分修改、可逆停用、不可逆注销；稳定 ID、院系归属、Asia/Shanghai 开放小时和星期验证 |
| D-02 座位 | 同上：按房间列出/登记、编号/插座/可用性修改、注销；全局稳定座位 ID，同房间编号唯一且注销后不重用 |
| D-02 权限消费 | [dependencies.py](dependencies.py)：调用真实当前身份 HTTP 适配器，执行院系及 `room:manage`/`operations:read` 权限检查；独立 M1 服务令牌只授予内部读 |
| D-02 持久化 | [001_master_data.sql](migrations/001_master_data.sql)：D 自有 schema 的房间/座位表、约束和索引；事务锁保护修改与级联注销；[seed.py](seed.py) 是独立幂等合成种子 |
| HTTP 入口 | [main.py](main.py)：保留 `GET /healthz`，数据库有配置时启动迁移，响应标识身份依赖模式 |

字段、鉴权、错误、兼容性、注销语义和示例的权威入口为 [d-master-data.md](../../contracts/d-master-data.md) / [OpenAPI](../../contracts/d-master-data.openapi.json)，版本 **0.1.0，proposed，代码已实现但待受影响组评审**。管理接口 `GET/POST /api/v1/rooms`、`GET/PATCH/DELETE /api/v1/rooms/{roomId}`、`GET/POST /api/v1/rooms/{roomId}/seats`、`PATCH/DELETE /api/v1/seats/{seatId}`；M1 只读网络接口 `GET /internal/v1/rooms` 与 `GET /internal/v1/rooms/{roomId}`。

## 验证证据

- 2026-10-22：在隔离本机 PostgreSQL 运行 `source .env.business-test` 后 `.venv/bin/python -m unittest discover -s services/d/tests -v`，**14 项通过**。10 项覆盖真实主数据数据库 CRUD/持久化、院系和权限隔离、验证边界、同室编号唯一与并发冲突、停用筛选、不可逆注销及引用保留、内部服务鉴权、迁移与种子重复执行；4 项覆盖真实 HTTP 身份客户端转发/异常、替身显式启用及生产拒绝。
- 身份成功响应由本机测试 provider 或显式开发替身提供；上述证据不代表真实 D-01 认证、会话失效、真实权限分配已集成。
- 同轮根 `bash scripts/check.sh` 已通过：新建 PostgreSQL 空库迁移、D 14 项及 M1 30 项测试、真实 M1→D HTTP 与 schema 权限隔离、两项关键行为变异检查、Vue 类型检查和构建均通过。生产构建的访客/只读预览浏览器回归通过；[实际业务Playwright验收](../../apps/web/tests/business.browser.cjs)也已通过：D房间/座位创建、编辑、注销及学生D管理页403守卫，JavaScript错误0。测试设置 `WEB_BUSINESS_TEST=1`、目标 `http://127.0.0.1:5173`，连接真实API与PostgreSQL、显式使用开发身份；见[综合验收记录](../m1/tasks/2026-10-22-completion.md)。真实D-01/03/04联调及当前业务部署仍未验证。
- 当前迁移：`001_master_data.sql`；仅隔离本机库有本轮证据。生产迁移、远端服务、release tag、部署环境均未验证。PR/提交和人工审批由根任务后续记录。

## 依赖与下一步

- `D-01` 未实现。当前身份响应采用消费方提案；[D02-IDENTITY 临时依赖清单](tasks/2026-10-22-d02.md#temporary-dependency-d02-identity) 正在使用。真实 HTTP 客户端已存在，无真实服务失败后的替身回退。M2 组提供契约与身份服务后由 M1/M2 联调、清理临时目录和激活配置并保留权限/错误测试。
- `D-03`、`D-04` 未实现，本任务没有新增通知或审计业务。
- D-02 管理页面由本轮 M1 前端任务提供；房间/座位创建、编辑、注销的真实API浏览器交互已通过，证据见[前端状态](../../apps/web/src/modules/d/STATUS.md)和[根任务](../m1/tasks/2026-10-22-completion.md)。M1 消费者须用网络接口验证最新主数据状态，不能读取 D 表或将静态契约当服务证据。
- 房间基础停用/注销不修改已有 M1 预约；M1 对新预约执行当前可用性和院系校验。存量预约治理、节假日/跨日开放规则、主数据变更通知需独立任务和契约评审。
- 合并前需要 D-02 主责与受影响消费组评审 schema、院系边界、权限假设及开放时间规则；具体审查人员尚未指定。`E-09` 的全组责任确认仍未完成。

## 最近交接

- 2026-10-22：[D-02 实现任务与临时依赖库存](tasks/2026-10-22-d02.md)，关联 D-02 / M1-01～03；当前仅 `m1` 工作树。
- 2026-10-22：此前骨架和 [D 归属 ADR 提案](../../docs/decisions/0002-d-ownership.md) 提供分工依据；本轮实现不追认提案为 Accepted。
