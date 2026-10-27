# M3 独立重建任务

> 归档记录：下文描述原 `工程伦理/Project1` / `codex/m3-rebuild` 工作区，测试与生产关闭结论不能直接代表本 develop 副本。2026-10-27 新适配范围见 [develop-integration.md](develop-integration.md)，当前依赖清单见 [dependencies.md](dependencies.md)，当前实现/验证见 [../STATUS.md](../STATUS.md)。

日期：2026-10-27。用户确认方案并明确要求实施；工作目录 `工程伦理/Project1`，工作分支 `codex/m3-rebuild`。不接续远程已有 m3 分支。

## 范围、基线与协作

需求：M3-01/02/03、X-01/03/04消费者、E-01/03/05/07。M3 全栈和真实网络写回适配；D/M1 的提供方业务不属于本任务。主机无 Docker，使用 SQLite 开发；另在任务目录启动隔离 PostgreSQL 16.2 实测，部署与 CI 配置 PostgreSQL 18。

允许：services/m3、apps/web/src/modules/m3；必要共享范围为契约、Python依赖与锁、公共HTTP技术层、M3代理、Compose/API启动、CI检查、需求与伦理追溯。集成由本次M3任务统筹；M3组验收业务，M1组评审写回契约，公共Web/部署维护组评审代理与流水线，D/schema相关负责人评审集成边界；尚无人工评审通过的证据。

M1 原始提交 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`。普通 Git 克隆两次网络失败，采用 GitHub 官方 codeload 同提交压缩包；Git文件树验证为 `1c9946ec9b599f8f6962f82bcd0afea42983ac1d`，恢复的原始 commit 对象 SHA 精确匹配指定提交，形成保留该提交的 shallow 基线，没有合成替代提交。origin=https://github.com/FDU-Group16/Project1.git。开始时无业务修改/冲突。因依赖M1/D，已尝试 fetch develop，结果见下方交付记录；此前只读API核实 develop 与m1同提交，不把该事实代替本次fetch结果。

已读根/Web AGENTS、任务模板、模块索引、M1/M3/D与M3前端STATUS、需求与M1契约。基线M1/D仅健康端点，D无业务契约，M1写回为0.1.0-proposed。

## 方案与验收

业务与接口以 [M3 契约](../../../contracts/m3-work-orders.md) 为准。选事务 outbox 加有界重试；待回执状态不提前宣布成功。SQLAlchemy/Alembic 统一 SQLite 开发与 PostgreSQL 迁移；正常模式禁用合成身份和成功回退。课程规模下工单、历史与评价保存在同一 JSON 聚合中，工单/幂等/outbox/guard 为独立表；通过 M3 guard 行串行化写入，不追求高并发吞吐。此取舍及扩展路径写入 README，测试覆盖跨线程/进程和独立数据库连接。

验收：全流程、返工、重派撤权、历次维修者防自验、取消和评价；真实HTTP适配失败/回执/重试，SLA边界、持久化、并发、迁移、重启；真实浏览器和窄屏；定向变异；根检查。真实M1多工单/M2/M1来源保留、D身份/目录和远端部署单列未验证。

## 临时依赖清单

| 标识 / 提供方缺口 | 精确临时范围与开启方式 | 替换条件与必须保留的内容 |
| --- | --- | --- |
| M3-D-DEV / D 身份、资源权限、房间和维修人员目录；无已评审业务契约 | `services/m3/dev_dependencies.py`、`seed.py`；`run-dev.sh` 的 `M3_MODE=development`、`M3_DIRECTORY_MODE=development`；前端 `apps/web/src/modules/m3/pages/M3Shell.vue` 的开发身份分支及 `session.ts`、`api.ts` 的演示会话装配 | M3、D 与公共 Web 负责人确认正式契约后实现 `ports.Directory` 真实适配、装配生产就绪条件，验证会话失效、资源范围、改派撤权，再移除合成身份/种子/开发配置。保留服务端鉴权、版本和前端请求隔离；不把开发 token 改名用于生产。 |
| M3-M1-DEV / M1 房间阻断写回；现有 `m1-room-blocks.openapi.json@0.1.0-proposed` | `services/m3/dev_m1_stub.py`；`run-dev.sh` 的 `M3_M1_MODE=development-http`、本地 3113 地址与合成服务 token；前端演示模式提示 | M3 与 M1 负责人评审并完成真实 `PUT /internal/v1/room-blocks/m3/{sourceId}` 后，用真实服务凭据与数据库验证全室下架、待验收保留、单来源释放、多工单及 M1/M2 限制保留，再移除开发服务和启动参数。保留 `m1_client.py`、worker、outbox、严格回执校验和持久化失败测试。 |

所有临时范围均在消费方目录标有 `TEMPORARY-DEPENDENCY`；清理属于获授权的后续联调任务，不据此跨模块改库。`tests` 中的外部 HTTP/目录测试夹具是长期消费方错误验证，不应与开发运行时文件一起删除。D 通知/审计本轮只保留 M3 结构化历史和管理员待办；将来的正式投递可消费已持久事件，不存在已发送到 D 的接口或证据。

## 交付记录

本次 develop fetch 已实际尝试，因 GitHub SSL 连接失败未获取 remote-tracking ref；最新远程状态未确认。继续在用户指定的已校验 M1 基线上独立开发，真实集成仍需合入前重新 fetch。未改写 main/develop 或远程已有 m3。

本轮实现已完成；新增内容尚未提交/推送，未创建 PR、合入 develop、打 tag 或部署。共享部分与 schema 已做独立 Agent 检查，不能代替相关负责人评审。交接范围和建议审阅顺序见 [评审说明](review.md)。

## 实际验证（2026-10-27）

| 执行项 | 结果与覆盖边界 |
| --- | --- |
| `bash scripts/check.sh` | 通过：M1 2 个/M3 15 个 OpenAPI 操作及引用、M3 契约漂移、四服务真实 HTTP 健康、M3 63 项、Vue 类型检查和生产构建（96 模块）。 |
| `.venv/bin/python -m pytest services/m3/tests -q`，默认 SQLite | 63 passed；真实 API、迁移重放、幂等、版本、权限、SLA、事务、线程/租约、真实 HTTP 回执及真实进程崩溃恢复。 |
| 同一套测试 + 专用 PostgreSQL 16.2 库 | 63 passed；M3 非超级用户、独立 `m3` schema、持久化、迁移重复运行和跨进程恢复。环境变量 `M3_TEST_DATABASE_URL`、`M3_REQUIRE_POSTGRES=1`、`M3_TEST_ALLOW_RESET=1`；只使用本任务可清空测试库。 |
| CI PostgreSQL 18 | 已配置两个工作流必须执行，失败阻止镜像构建/部署；未推送，因此没有远端运行结果。本机 16.2 证据不能记为 18 通过。 |
| `python scripts/test-staging-images.py` 与 Bash 语法检查 | 9 passed；本机未运行 Docker 构建/Compose/远端迁移。Nginx 启动依赖 M3、同源 context 健康探测与开发数据库打包排除已修正并审查。 |
| uv 0.10.0 冻结安装 | 与 Docker/CI 一致的精确 uv 版本在新的独立空环境中 `uv sync --frozen` 成功，28 个包；锁文件 revision 5 已被该版本实际解析、安装。 |
| `node services/m3/tests/browser-flow.cjs http://127.0.0.1:5173` | 真实 Chrome + 真实 M3 + 明示的本地 M1 HTTP 替身通过：上报/派单/开工/完工/返工/管理员代验/回执关闭/一次评价/刷新/身份隔离；1440/768/375/320px 无横向溢出、无 JS 错误，键盘焦点和 M1/M2 路由正常。 |
| `node apps/web/tests/interface.browser.cjs http://127.0.0.1:5173` | 原有七组浏览器回归通过：首页、路由/错误页、登录入口、M1 筛选/预约示例、返回、手机菜单及窄屏。API 检测仅排除已实现的 M3，不放开 M1/M2 未提供端点。 |
| `.venv/bin/python services/m3/tests/mutation_check.py` | 正常目标 3 passed；权限放开、提前进入维修、绕过回执校验 **3/3 均被测试发现**；隔离副本执行，主工作区源码摘要未变。见 [独立审查](independent-review.md)。 |

pytest 的一个 Starlette/TestClient 弃用提示不影响结果，当前实际 HTTP 传输与服务测试均通过；后续框架升级单独处理。所有 HTTP 提供方夹具只验证 M3 消费行为，不证明真实座位可用性变化。

浏览器测试需可用的 Playwright 和 Chrome；不新增业务 npm 依赖，可通过 `NODE_PATH` 指向独立工具环境。当前运行依赖位于任务上层 `.tooling`，截图保存在上层 `.verification/screenshots`（不纳入业务仓库），含桌面工作台、报修表单、完成页和手机完成页。修正了测试中同名房间筛选的路由等待竞态，以及共享测试把 Vite 源码 `/src/shared/api/http.ts` 误识别为业务调用的问题；没有删除实际权限或流程断言。

## 需求与证据映射

- M3-01：`main.py`/`service.py`、`test_api.py` 创建/幂等/权限/取消，`test_independent.py` 重派撤权；Vue 三页与浏览器报修/派单。
- M3-02：`service.scan_sla`/worker、独立测试中的精确边界/并发去重/返工阶段；管理员超时视图。D 消息投递未完成。
- M3-03：动作状态机与历次参与者约束，API/独立测试验收/自验/评价，浏览器返工与代验；M1 回执前不关闭。
- X-01/03/04：消费者真实网络适配、严格回执、有界重试、独立来源和进程恢复测试；真实 M1 全室座位与其他来源验证仍未完成。
- E-01/03/05/07：局部 AGENTS、需求/契约/状态、Alembic `0001`、独立种子、CI 门禁、定向变异与可重跑行为测试。人工验收、PR、远端 CI/迁移/发布证据仍待交付流程产生。

## 14:20 后续集成可行性复核

用户询问本地网址来源及能否接入 `https://pj1.756888.xyz`，本轮仅解释并只读核对，未发起合并或部署。重新执行 `git fetch origin refs/heads/develop:refs/remotes/origin/develop` 成功；远端跟踪 SHA 为 `13dcd59f9a46c859f8593b530d7aa54c27faaf1f`（该提交时间 2026-10-27 14:18:14 +08:00）。当前分支仍为 `codex/m3-rebuild`，HEAD 仍是 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`，本地全部未提交实现保留；未将远端代码合入或当作当前实现的一部分。

只读 `git show origin/develop:...` 核对全局规则、M1/D STATUS、实现、契约与 D 分工：

- M1 已新增真实预约与 `PUT /internal/v1/room-blocks/m3/{sourceId}` 提供代码，写回契约升级到 `0.2.0-proposed`，保留原请求/响应形状并明确冲突和服务身份；消费者仍须实测日期精度、回执、服务凭据与多来源限制，不能直接宣称兼容通过。
- D-02 已有房间/座位 HTTP API；D-01 身份仍未实现。公共 Web 已增加身份状态与真实身份消费入口，M3 后续应接入这些共享入口，并适配房间资源范围、维修人员目录和权限，替换本地合成目录。
- 最新 ADR 已登记 M1→D-02、M2→D-01、M3→D-03/D-04。此前本轮方案将 D 通知/审计排除在工单任务之外，因此这两个公共子域并未实现；后续需要据最新分工另行明确契约和实施范围。旧记录中的“D 归属提案”只描述原基线。
- develop 还新增临时依赖登记与检查、公共 HTTP/登录、启动工具及测试；M3 合入时需兼容这些共享变化，补本模块依赖登记，不能整体覆盖旧基线同名文件。
- 线上首页可访问；只读 `GET https://pj1.756888.xyz/api/m3/v1/context` 返回 HTTP 404。此证据仅表示该路由当时不可用，不证明线上 M1/D 业务或部署 SHA。

本地 `http://127.0.0.1:5173/m3` 来自 Vite 的 5173 端口和 Vue `/m3` 路由，只在当前电脑开发服务运行时可用。接入现有网站后的预期页面是 `https://pj1.756888.xyz/m3`，浏览器同源 `/api/m3/` 经 Nginx 转发 M3 容器；无需新域名。当前代码若直接按 production 部署，M3 页面将显示“报修服务准备中”，因为正式目录装配与共享登录尚未接好；仅填写数据库和 M1 环境变量不能启用。下一步为针对最新 develop 的集成适配、真实 M1/D-02 联调、D-01 就绪后的身份接入，以及数据库/CI/评审后的部署。当前没有执行这些后续变更。
