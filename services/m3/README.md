# M3 物业报修工单

本模块实现报修、派单/重派、维修、验收/返工、一次评价、超时升级和持久化网络写回。当前独立交付副本基于 `origin/develop@13dcd59`，包含真实 M1 写回和 D-02 主数据，并新增 M3 的真实 HTTP 身份/房间/人员目录适配。接口以 [M3 契约](../../contracts/m3-work-orders.md) 和 [目录消费提案](../../contracts/m3-directory-dependencies.md) 为准；D-01 正式提供方仍缺失，D-03/04 未实现，验证与上线状态见 [STATUS](STATUS.md)。未配置正式依赖时只响应健康和上下文，远端失败不回退演示。

## 本地开发

仓库根目录完成 `uv sync --frozen` 后运行：

```bash
bash services/m3/run-dev.sh
```

脚本启动两个独立进程：`127.0.0.1:3103` 上的 M3 API，以及 `127.0.0.1:3113` 上的 M1 HTTP 契约替身。后者只保存合成来源回执，不具有真实座位逻辑。浏览器端按公共 Web 开发说明显式开启 `VITE_USE_DEV_IDENTITY=true` 后执行 `npm --prefix apps/web run dev`，使用共享 `/login` 登录，再打开 `/m3`。M3 不提供第二套前端身份切换。角色顺序：学生报修 → 维修管理员派单 → 受派维修员开工/完工 → 原学生验收评价；更换身份先退出共享会话再登录。后台 worker 通过真实 HTTP 处理替身回执。

开发数据库为忽略版本控制的 `services/m3/.local/work-orders.sqlite3`，重启后保留。`GET /api/m3/v1/context` 展示当前依赖模式；`businessReady` 只表示本地装配，不能证明远端就绪；`/healthz` 仅表示服务可响应。共享开发登录对应公开合成 token `dev-student-cs/ee`、`dev-repair-admin`、`dev-technician-1/-2`，ID 与 token 一致。旧 `demo-reporter[-2]`、`demo-admin`、`demo-technician[-2]` 保留供 API 回归，不是正式凭据；开发房间为合成数据。

首次业务库为空。需要可重复的演示种子时，在完成迁移后单独运行以下命令；种子通过真实业务服务和稳定幂等键创建两张合成工单，重复运行不重复插入，不进入迁移或部署启动流程：

```bash
M3_MODE=development M3_DIRECTORY_MODE=development \
M3_DATABASE_URL=sqlite:///services/m3/.local/work-orders.sqlite3 \
.venv/bin/python -m services.m3.seed
```

## 状态、权限和计时

`SUBMITTED → ASSIGNED → BLOCK_PENDING → IN_PROGRESS → PENDING_ACCEPTANCE → RELEASE_PENDING → CLOSED`。M1 ACTIVE/RELEASED 回执分别完成两个等待状态。完工待验收保留下架；拒绝验收回到维修中，重新计时，仍保留原下架来源。创建或派单状态可取消，开始维修后不可取消绕过验收。

原报修人验收；管理员代验必须说明理由。历次实际维修参与者均不能验收，即使后来被改派或获得管理员角色。管理员可在待派单、已派单、维修中派单；重派不重置 SLA，旧维修员即时撤权。只有原报修人能在关闭后进行一次 1～5 星评价。

创建后 24 小时未派单、首次派单后 48 小时未完工（含等待下架回执）升级；`now >= dueAt` 为边界，每阶段一次。返工开始新 48 小时阶段；待验收不自动关闭或通过。升级仅进入 M3 持久历史和管理员待办，未接入 D 通知，不能当作消息送达证据。

## 配置与持久化

| 环境变量 | 默认值及用途 |
| --- | --- |
| `M3_MODE` | `production`；开发必须显式 `development` |
| `M3_DIRECTORY_MODE` | `unavailable`；正式适配显式 `http`，合成目录显式 `development` |
| `M3_IDENTITY_BASE_URL` | 无默认；D-01 身份与维修人员目录 HTTP 基址 |
| `D_BASE_URL` | 无默认；D-02 公开房间 HTTP 基址，携带当前用户 Bearer |
| `M3_DIRECTORY_TIMEOUT_SECONDS` | `3`；目录请求超时 |
| `M3_DATABASE_URL` | 无默认；SQLite 仅开发/测试，正式使用 `postgresql+psycopg://...` |
| `M3_M1_MODE` | `http`；本地脚本显式 `development-http` |
| `M3_M1_BASE_URL` / `M3_M1_TOKEN` | 无默认；真实 M1 地址与服务凭据从安全环境注入 |
| `M3_WORKER_ENABLED` | `true`，仅业务目录已显式启用时生效 |
| `M3_WORKER_INTERVAL_SECONDS` | `1` |
| `M3_ASSIGNMENT_SLA_HOURS` / `M3_REPAIR_SLA_HOURS` | `24` / `48` |
| `M3_M1_TIMEOUT_SECONDS` | `3` |

`python -m services.m3.migrate` 根据 `M3_DATABASE_URL` 调用 Alembic 从空库升级到最新版本。业务装配执行同一幂等迁移器；正式启动脚本在服务前显式迁移，失败阻止启动，不能用手工建表代替。PostgreSQL 使用独立 `m3` schema（含 Alembic 版本表），必须使用 M3 独立数据库账号。迁移没有破坏性 downgrade；正式发布需备份及兼容性评审。正式数据库与开发数据库分离；工单私有依赖来源标记会阻止生产启动处理开发或未标注旧工单，不自动改标签或删除原数据。

数据库事务以 M3 专用 guard 行串行化写入；SQLite 使用 `BEGIN IMMEDIATE`。这是课程规模下以写吞吐换取简洁一致性的取舍；列表和 SLA 扫描仍遍历本模块工单。规模扩大时可将状态/版本与调度列规范化，按工单行锁、独立幂等约束和 outbox `SKIP LOCKED` 领取，再加入分页与索引化 SLA 查询；不能只删除 guard 而保留现有读改写过程。

## M1 写回与失败恢复

客户端严格遵循 `m1-room-blocks.openapi.json@0.2.0-proposed`：稳定工单来源、ACTIVE revision 1、RELEASED revision 2；重试保持完整原请求和关联 ID。`M3_M1_TOKEN` 与提供方 `M1_M3_TOKEN` 配对，必须与 M2 凭据区分。客户端拒绝重定向，不把令牌转发给重定向目标；校验全部回执字段、版本类型、状态、来源、房间、UTC 时段及 `appliedAt`，限制回执大小。

网络异常及 502/503/504 最多自动尝试 5 次，间隔 1/5/30/120 秒。401/403/404/409/422、其他非 200 或损坏回执停止；工单保留等待状态。管理员仅能对暂时错误预算耗尽执行 `retry-sync`，开启新的有界尝试批次并记入历史，原请求不变。永久错误需相关模块核对来源/身份/房间和已经应用的状态，不能靠改库、伪造回执或随意增加版本绕过。

worker 在发送前持久化尝试次数与租约；崩溃、重启和多 worker 仍受预算约束。ACK 提交重新读取当前工单，保留同时发生的 SLA 历史；丢失租约的旧 worker 不能确认新租约。网络已成功但本地提交失败时，租约到期重放同一幂等请求。

## 反向代理与正式接入

浏览器只通过同源 `/api/m3/` 访问 M3：本地由 Vite 代理到 `127.0.0.1:3103`，部署由 Nginx 代理到内部 `m3-api:3103`。路径前缀必须保留，并转发用户原本的 `Authorization`；代理不能替浏览器注入管理员身份。M1 的服务 Bearer 仅保存在后端安全环境，不进入 Vue 配置、响应、日志或浏览器存储。本模块不使用 `X-Forwarded-*` 决定业务身份/权限，不能通过代理头授予角色。若部署启用 Uvicorn 代理头信任，应仅信任已知入口代理，不能把任意来源头作为可信客户端证据。

正式 HTTP 适配与装配已实现，完整配置可启用 production，但仅填写变量不能弥补尚未实现的 D-01 提供方。上线仍需要：

1. M2/D-01 提供正式身份验证、登录会话与维修人员目录；共同评审 [目录消费提案](../../contracts/m3-directory-dependencies.md) 中 repair 权限。`room:manage` 和 `operations:read` 不授予 M3 管理权，不能把开发 token 改名用于生产。
2. 显式配置 `M3_MODE=production`、`M3_DIRECTORY_MODE=http`、`M3_IDENTITY_BASE_URL`、`D_BASE_URL`。逐请求访问 D-01 验证身份，以用户 Bearer 访问 D-02 公开房间，保留其范围过滤；不借用 `D_M1_TOKEN`。401/403 原样映射，远端不可用或响应错误为503；真实故障无合成回退。
3. 配置 M3 专属 PostgreSQL 账号并执行 Alembic，配置真实 M1 网络地址与最小写回权限凭据；在同一版本窗口验证 ACTIVE/RELEASED 回执、重放、故障恢复，以及其他工单/M1/M2 限制保留。健康端点成功不能替代这些业务检查。
4. 获得实际联调证据后移除清单内的开发目录、种子、独立 HTTP 替身和临时启动配置，保留正式接口、事务 outbox、校验与回归测试，更新 STATUS 的实现/测试/部署证据。

## 验证与替身替换

```bash
.venv/bin/python -m pytest services/m3/tests -q
bash scripts/check.sh
```

核心 API 测试可原样在专用 PostgreSQL 测试库再次执行：安全环境提供 `M3_TEST_DATABASE_URL`，显式设置 `M3_TEST_ALLOW_RESET=1`、`M3_REQUIRE_POSTGRES=1`。额外设置 `M3_REQUIRE_SCHEMA_OWNER=1` 会强制验证账号只拥有预建 `m3` schema、没有数据库级 CREATE 权限，并确认重复迁移不会再次请求创建 schema。测试会清理该库的 M3 测试业务数据，绝不能指向生产或共享集成库。未提供 URL 时本地测试使用 SQLite；通过 SQLite 不是 PostgreSQL 验证。

开发目录、HTTP 替身及启动脚本是消费方临时依赖。真实 M1/D-02 联调脚本为 `tests/integration_real_providers.py`，它通过独立 HTTP 身份夹具绕开尚未提供的 D-01，仅这部分明确为替身。全部正式提供方验收后按清单清理临时启动路径，保留真实业务、outbox、HTTP 客户端与错误测试。当前清单见 [docs/dependencies.md](docs/dependencies.md) 和 [DEPENDENCIES.json](DEPENDENCIES.json)，本次范围见 [develop 适配记录](docs/develop-integration.md)；旧 implementation.md 只保存原工作区验证历史。
