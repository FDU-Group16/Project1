# M3 模块状态与交接（develop 适配副本）

更新时间：2026-10-27。当前副本 `工程伦理/develop/Project1`，分支 `m3-develop`，基线 `origin/develop@13dcd59f9a46c859f8593b530d7aa54c27faaf1f`。原重建目录保持不动。范围与评审责任见 [适配记录](docs/develop-integration.md)；[依赖登记](DEPENDENCIES.json) 与 [精确清单](docs/dependencies.md) 记录未完成提供方，不以旧工作区验证替代本轮证据。

## 当前实现

- 已迁入 M3-01/02/03 全流程、SLA、权限、幂等/版本、Alembic `0001`、事务 outbox、有界重试和进程恢复；状态与接口见 [M3 v1](../../contracts/m3-work-orders.md)。未修改 M1/D 提供方业务。
- `http_directory.py` 真正通过 HTTP 逐请求验证 D-01 身份，使用用户令牌读取 D-02 公开房间及待提供的维修人员目录；完整可信权限支持多角色，不能通过房管/运营角色获得维修管理员权。目录调用位于数据库事务外，提交时重查版本和权限。
- production 已支持显式 HTTP 目录与 PostgreSQL 装配；默认未配置仍拒绝业务。远端失败返回401/403/503，不回退；生产启动拒绝开发或来源不明旧工单，防止演示 outbox 写入真实 M1。`/healthz` 保持原语义，`context.businessReady` 仅表示本地装配。
- M1 网络消费者按 `m1-room-blocks.openapi.json@0.2.0-proposed` 适配，使用 M3 独立服务凭据。D-02 已有基线实现；D-01 仍缺失，维修权限/人员目录为 [0.1.0 消费提案](../../contracts/m3-directory-dependencies.md)，不声称提供方完成。
- Web 改用共享登录；开发目录仍显式支持共享 dev ID 与原 API 回归身份。M3 组负责的 D-03/D-04 本轮没有新增实现或假投递；工单历史与超时待办不等于公共审计或通知送达。

## 本副本已执行验证

- `.venv/bin/python -m pytest services/m3/tests/test_api.py services/m3/tests/test_http_directory.py -q`：SQLite **45 passed**（26 原 API/迁移边界 + 19 新 HTTP 目录边界）。覆盖每请求会话验证、房管/运营越权、报修资格、多权限防自验、撤销维修权、用户令牌与可见房间过滤、派单目录网络事务隔离/版本竞态、401/403/故障映射、无效目录、重定向/超时、防演示数据转生产。重复迁移不再请求已有 schema 的数据库级 CREATE 权限；真实 schema-owner 验收由集成任务执行。
- `.venv/bin/python scripts/check-dependencies.py --consumer M3`：**0 错误**；D-01/D-03/D-04 缺口和 M1 待完成消费者集成被如实报告，登记通过不等于真实提供方验收。
- 本副本根检查通过：SQLite **83 passed**、PostgreSQL **16.2** 独立 schema owner **83 passed**；真实 M3→M1→D-02 HTTP 链路、来源保留与六项数据库隔离通过；既有 M1/D 回归和定向变异通过。详情见 [适配记录](docs/develop-integration.md) 与 [真实提供方证据](docs/real-provider-integration.md)。PG18/Docker/远程CI仍待执行。共享登录/真实三服务浏览器、既有 M1/D 业务、M2 页面、客户端六组回归均通过，JavaScript 错误 0；原下文 63 项只属于旧基线。
- 没有提交/推送、PR、合并、远端 CI、Docker/服务器部署或人工评审通过记录。

## 下一步与边界

M1/D-02 真实网络与来源保留验收使用独立测试 PostgreSQL 和明确 D-01 HTTP 身份夹具，D-01 正式登录/会话/人员提供方仍须 M2 实现并评审提案。最终正式依赖验收后清理开发目录与 M1 替身，保留消费者错误测试。D-03/D-04 按已确认分工另行明确实施范围；上线还需数据库账号/迁移、相关负责人评审和部署流水线证据。

---

## 归档：以下仅为原工作区独立重建历史

更新时间：2026-10-27。本轮从 `m1@99ce858a2bbf8caa2f4b226a83f989c54d6992d1` 独立实施；不是沿用远端已有 m3 分支。任务范围与临时依赖见 [实施记录](docs/implementation.md)，API 见 [本轮契约](../../contracts/m3-work-orders.md)。下方旧骨架记录保留为历史，不能代表本轮业务状态。

**14:20 依赖复核更新**：已成功 fetch `origin/develop@13dcd59f9a46c859f8593b530d7aa54c27faaf1f`，只读确认远端新增 M1 业务与房间写回（契约 `0.2.0-proposed`）、D-02 主数据及公共身份消费入口。它们尚未合入本工作区，M3 尚未真实联调；此前“提供方只有骨架”的描述仅针对指定基线。D-01 仍未实现；最新分工将 D-03/D-04 归 M3 组，本轮工单实现未包含这两个公共子域。详见实施记录末尾。

## 本轮已实现

- M3-01/02/03：上报、权限与可见范围、创建幂等、派单/重派、维修、验收/返工、取消和一次评价；维护历次维修参与者以防自验，服务端执行版本与状态校验。
- SLA：未派单 24h、派单后未完工 48h；精确边界、阶段去重、返工新阶段，M3 历史和管理员待办持久化。D 通知/共享审计未实现。
- SQLAlchemy + Alembic `0001`：M3 专属工单/幂等/outbox/事务guard，PostgreSQL `m3` schema 与 SQLite 开发映射；无 `create_all` 或手工建表。
- X-01/03/04 消费方：严格真实 HTTP 适配，持久租约与有界重试，确认 ACTIVE 后进入维修中、确认 RELEASED 后关闭；未调用真实 M1 提供方。
- `/api/m3/v1/context`、`me`、`rooms`、`technicians`、工单列表/详情/创建及八种动作；`/healthz` 保留骨架响应。
- 显式开发目录与独立进程 M1 HTTP 替身；正常模式不启动业务/worker、不打开开发数据库、不模拟成功。运行见 [README](README.md)。

## 本轮实际验证

- `.venv/bin/python -m pytest services/m3/tests/test_api.py -q`：25 passed（2026-10-27，本机 SQLite）；覆盖真实 API 状态流程、权限、幂等、严格输入、验收理由、回执前等待、返工、取消、一次评价、Alembic 重复迁移、独立幂等开发种子、默认模式隔离及无效服务配置永久停止。
- 最终全量 `.venv/bin/python -m pytest services/m3/tests -q`：SQLite **63 passed**，本机隔离 PostgreSQL **16.2：63 passed**。包括真实网络回执/错误、并发/SLA、迁移及真实子进程异常退出后恢复；详见 [独立审查](docs/independent-review.md)。CI 已强制 PostgreSQL 18 检查，但尚无远端执行结果。
- `bash scripts/check.sh`、Vue 类型/生产构建、9 项原有部署脚本测试、真实浏览器全流程与原有七组界面回归通过；定向变异 **3/3 被测试发现**，未修改主工作区被测代码。完整命令与边界见 [实施记录](docs/implementation.md)。
- 真实 M1/D、全室座位与跨模块来源保留、人工验收、Docker 构建/远端迁移、提交/PR/合并与发布仍未验证。当前只在本地新分支工作区实现，未改动 M1/M2/D 业务。

## 集成缺口与下一步

M1 写回仍是 `0.1.0-proposed`；D 身份/房间/维修人员目录没有正式契约或提供方。合成目录 `dev_dependencies.py`（M3-D-DEV）、独立网络替身 `dev_m1_stub.py`（M3-M1-DEV）及 `run-dev.sh` 只服务本地验证；替换须由集成任务确认授权、适配正式契约、完成真实来源/权限测试，再按清单清理。M3 正式数据库账号、迁移/部署证据及真实通知审计仍待相关负责人集成。

---

## 初始骨架历史

更新时间：2026-10-22。本文记录当前工作区事实，不代表已经提交、人工验收或发布。

## 已实现

- 独立 ASGI 入口 `services.m3.main:app`，见 [main.py](main.py)。
- 使用 [公共 HTTP 骨架](../common.py) 提供健康检查，尚无业务路由。

## 接口状态

| 接口 | 状态 | 调用方与说明 |
| --- | --- | --- |
| `GET /healthz` | 已实现，可本地验证 | HTTP 200；响应 `{"service":"m3-api","status":"ok"}`。仅表示 HTTP 应用可响应，不检查数据库或业务依赖。 |
| M3 报修、派单、维修和验收等业务接口 | 未定稿、未实现 | 尚无可供前端或其他模块调用的业务接口。 |
| 调用 M1：`PUT /internal/v1/room-blocks/m3/{sourceId}` | 拟议，双方均未实现 | M3 是未来调用方，M1 是提供方；本模块尚无 HTTP 调用适配或重试流程。 |

写回接口以 [M1 OpenAPI 契约](../../contracts/m1-room-blocks.openapi.json) `0.1.0-proposed` 为准；字段、幂等、版本及错误约定见 [契约说明](../../contracts/README.md)。提案待评审，不能据此宣称接口可用。

## 验证证据

- 2026-10-22 根 [检查脚本](../../scripts/check.sh) 已通过；其中 [HTTP 冒烟检查](../../scripts/smoke.py) 启动真实 M3 进程并核对健康响应。
- 此证据覆盖骨架健康行为，不包含维修流程、状态写回、数据库或远端部署验证。

## 依赖与未完成

- [M3-01～M3-03](../../docs/requirements.md)：故障上报与派单、维修超时升级、验收与评价均未实现；角色和状态流程尚待细化。
- `X-01`、`X-03`、`X-04`：未来经网络请求 M1 下架整室座位，并在验收通过后释放对应来源；多工单并存及恢复条件仍需决策。
- `D-01`、`D-02`：未来依赖 D 的身份权限和稳定房间主数据；相关能力未实现，D 责任归属仍为提案。
- 数据库业务表、独立 schema/账号及版本化迁移未建立；不能把健康检查视作持久化验证。

## 最近交接

- 2026-10-22：登记初始骨架及未来 M1 写回依赖，供其他模块判断当前可用范围。对应提交、人工验收和远端发布记录未登记。
