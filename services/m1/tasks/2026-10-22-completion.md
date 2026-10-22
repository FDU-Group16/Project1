# M1 与 D 剩余需求实施计划

日期：2026-10-22。授权：完成剩余 M1 和 D，按需求提交且仅在 m1 分支。

## 范围、协作与同步

M1 依赖 D 身份、主数据、通知和审计，触发 develop 检查。允许 services/m1、services/d、Web 的 M1/D 模块、必要的共享认证/HTTP/路由/代理、contracts、需求/伦理/实施决策、依赖与验证/持久化配置。M2/M3 业务代码/测试/状态不在范围内；不合并 develop/main，不发布。
原 develop 工作区存在未提交启动器改动，全部保留；独立工作区 `.worktrees/m1` 检出既有 m1 分支。无冲突、未完成合并或 rebase。2026-10-22 从现有 origin (https://github.com/FDU-Group16/Project1.git) 显式 fetch develop 成功，远程 SHA 与实际 HEAD 均为 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`，已包含，无需更新分支。
已读取根/Web AGENTS、模块索引、M1/D/Web 状态、任务书、需求、任务模板、ADR0001/0002、room-blocks v0.1.0-proposed。现有业务接口均未实现。用户随后明确：只实现 M1 和 M1 负责的 D-02；D-01/03/04 作为接口依赖。默认业务规则已获本次用户确认，见 ADR0003。

## 方案、提交与验收

1. 需求/契约/决策先行：明确首版规则、接口、迁移和验收，保留团队评审状态。
2. D-01 消费方接口与显式临时开发身份（不实现 D-01 提供方）。
3. D-02：独立数据库 schema、可重放迁移、幂等合成种子、房间/座位管理及界面。
4. D-03/D-04 消费方发件箱与错误重试，实际通知/审计提供方不在范围内。
5. M1-01：院系权限；M1-02：时间/可用性/插座搜索；分别提交。
6. M1-03：整点、最长4小时可配置、并发冲突与取消。
7. M1-04：每日房间编码和 Web 签到。
8. M1-05：持久化调度、两次提醒、违约释放及重试幂等。
9. M1-06：个人历史/再次预约；M1-07：运营事实与统计；分别提交。
10. M1-08 / X-01～04 提供方：真实 HTTP 写回、来源、版本墓碑与多来源限制；不声称 M2/M3 消费端完成。
11. 真实 D↔M1 HTTP 和前端验收，迁移重放、并发、越权、失败路径，bash scripts/check.sh，关键行为变异验证，更新交接。

API 使用 UTC、稳定 ID 和 [start,end)。服务仅访问本服务 schema，跨服务通过 HTTP；正常运行不能模拟成功。每项需求同批更新实现/契约/测试/前后端状态，按需求提交到 m1。共享改动由 M1 集成，D 各子域拟议维护组和 M1/M2/M3 消费组在合并前评审，具体人工人员待团队登记；提交不代表批准或部署。临时依赖若需要，按任务模板明确清单、配置、替换条件及保留业务代码。

## 最终实现与自动验收

- M1-01～08 后端按单个需求提交；前端按搜索预约、签到历史、违约、统计、来源流程分批提交。D-02 后端与管理界面单独提交。
- `bash scripts/check.sh`（2026-10-22）最终通过：26 个契约操作/本地引用、四服务真实健康检查、全新隔离 PostgreSQL 迁移及业务测试（D 14 项、M1 30 项）、真实 M1→D-02 HTTP、Vue 类型检查与生产构建。
- 真实 HTTP 验证：D 房间/座位创建、院系和预约所有权隔离、幂等重放、两用户并发抢座、M2 冲突拒绝、M3 保留已有预约、多来源释放、旧版本拒绝、D 服务故障503；M1/D 数据库账号不能访问对方 schema。身份仍为显式开发替身。
- 变异验证：在进程内故意放开院系授权、移除预约冲突检查，两项对应测试均断言失败；恢复原实现后均通过。源文件未保留缺陷。
- 独立复查修复了：D 响应缺字段被误当公共房间、重定向转发凭据、失败重试投递过期提醒。回归覆盖严格响应/ID校验、301/302/303/307/308 不转发、取消/签到/过期后 SUPPRESSED。
- 迁移：D `001_master_data.sql`，M1 `001_reservations.sql`、`002_outbox_receipts.sql`、`003_suppressed_reminders.sql`；空库顺序重放及重复执行通过，种子独立且幂等。
- 生产构建浏览器回归：7组检查、1440/768/430/375/320px，无JavaScript错误；正式入口转真实登录、不提供开发身份、不渲染演示房间；旧显式预览、历史/导航/焦点正常。
- 真实业务浏览器：`WEB_BUSINESS_TEST=1 NODE_PATH=<已有Playwright依赖目录> node apps/web/tests/business.browser.cjs http://127.0.0.1:5173` 全部通过。真实 Web→D/M1→PostgreSQL 覆盖房间/座位创建、编辑、注销，插座筛选、预约/取消/再次预约，身份切换后他人详情404且页面不残留、学生管理守卫403，实际统计、来源与每日编码展示；JavaScript错误0。使用显式合成身份，未拦截业务接口；实际签到与调度边界由后端固定时钟行为测试覆盖，不混称浏览器实时签到验收。早先自动化连接挂起已中断，最终证据来自可复跑的 Playwright 脚本。
- 一键开发命令 `uv run python -m services.m1.temporary_dependencies.run_demo` 在新建独立 PostgreSQL 成功启动 D、M1、调度器和 Vite；同一业务浏览器脚本在该新库再次全部通过。Ctrl+C 正常停止四个子进程，合成发件箱标记为 SIMULATED。临时验收数据库及凭据文件已清理；演示数据库已停止并保留，忽略的本机随机配置保留供下次启动，不纳入提交。
- 最后 `git diff --check`、新增浏览器脚本语法及改动 Markdown 本地链接检查通过。

## 剩余边界与交接

本次完成 M1 与 D-02 的本地代码和上述验证。D-01/03/04 的真实身份、通知、审计不在用户授权范围；消费者适配和发件箱已实现，实际授权/投递/审计存储联调仍未验证。M2/M3 提供方应用、补偿流程和部署端到端未验证。主数据远程读与预约事务之间的并发变更窗口仍需跨组集成时评估事件/版本协调，未声称分布式强一致。

普通运行只用真实依赖；开发替身路径/启动/移除清单见后端临时依赖README、D-02任务和Web身份库存。`services/m1/temporary_dependencies/run_demo.py` 显式启动本机合成演示，不是正常发布配置。

人工验收/契约批准/具体评审人、PR、部署tag、发布和生产迁移证据：未提供或未执行。未修改 M2/M3 业务/状态，未合并 develop/main，未推送或发布。原 develop 工作区的 README、Web状态、需求、本地启动器及其任务记录保留。首次 fetch 的日期和 SHA 已记录，精确时分秒未记录。

## 按需求提交记录

以下均为本地 m1 分支；最终集成验收提交另见 Git 最新记录。

| 提交 | 需求与内容 |
| --- | --- |
| `60bbb0a` | docs(M1,D-02): define scoped delivery plan and acceptance rules |
| `7ec2326` | docs(M1,D-02): specify public APIs and room writeback compatibility |
| `4698627` | feat(D-02): persist scoped room and seat master data with replayable migrations |
| `91c3911` | feat(M1-01): validate trusted identities and isolate department access |
| `d1b1687` | feat(M1-02): search available seats by time and socket |
| `65d6fd6` | feat(M1-03): serialize reservations and enforce duration and cancellation rules |
| `18ac1dd` | feat(M1-04): verify daily room codes and check-in deadlines |
| `21d1974` | feat(M1-05): persist reminders no-shows and retry-safe delivery |
| `a94e0b9` | feat(M1-06): expose private history and revalidate repeat bookings |
| `5520627` | feat(M1-07): aggregate room and seat reservation facts |
| `9821db1` | feat(M1-08): apply versioned room blocks and retain source provenance |
| `adc0752` | feat(web): consume identity contracts and configure public API proxies |
| `23e7672` | feat(D-02): add room and seat administration pages |
| `756bd4d` | feat(M1-01,M1-02,M1-03): connect seat search and reservation forms |
| `1c0e850` | feat(M1-04,M1-06): add check-in and private reservation history |
| `9d719b7` | feat(M1-05): show paginated breach history |
| `af67c86` | feat(M1-07): show room and seat reservation statistics |
| `2357b74` | feat(M1-08): expose room code display and source provenance |
