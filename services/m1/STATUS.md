# M1 模块状态与交接

更新时间：2026-10-22。本文说明 m1 工作区实现及验证，不代表人工验收、合并到 develop 或部署。主任务：[按需求完成M1与D-02](tasks/2026-10-22-completion.md)；详细验证：[后端验收记录](tasks/2026-10-22-backend-verification.md)。

## 已实现

| 需求 | 行为与源码 | 可用入口 |
| --- | --- | --- |
| M1-01 | 可信身份 HTTP 消费适配、显式开发替身、院系与资源权限；`dependencies.py`、`core.py` | 所有公开接口使用Bearer身份；搜索和直接预约均检查院系；D-01 身份提供方仍未实现 |
| M1-02 | 开放时段/插座/可用性/个人预约/来源阻断筛选；`search.py` | `GET /api/v1/seats` |
| M1-03 | 整点预约、4小时可配置、7天窗口、事务锁、幂等、取消；`reservations.py` | settings；create；cancel |
| M1-04 | 房间每日HMAC编码、本人限定签到；`checkin.py` | check-in-code；check-in |
| M1-05 | 持久化调度、提醒、违约释放、通知/审计发件箱重试、过期提醒SUPPRESSED；`scheduler.py` | `python -m services.m1.scheduler [--once]` |
| M1-06 | 本人当前/历史/详情/违约、再次预约重新校验；`history.py` | reservations；detail；rebook；breaches |
| M1-07 | 受控房间/座位事实统计与预约小时数；`operations.py` | `GET /api/v1/operations` |
| M1-08、X-01～03提供方 | M1/M2/M3来源、版本与墓碑、来源并集；`blocks.py` | `PUT /internal/v1/room-blocks/m2/{sourceId}`、m3；room provenance |

M2有效占用与已有个人预约冲突返回409；M3下架保留已有预约并拒绝新增。以上为用户同意的首版实施规则，团队评审仍待完成。M2/M3消费端未在本任务中实现或修改。

## 契约、持久化与入口

- [公开接口](../../contracts/m1-public.md) / [OpenAPI](../../contracts/m1-public.openapi.json)：v0.1.0-proposed，已实现消费方业务；真实D-01/D-03/D-04未联调。
- [写回契约](../../contracts/m1-room-blocks.openapi.json)：v0.2.0-proposed，保留v0.1请求/响应形状，明确冲突策略和独立服务身份；M1提供方已实现，真实M2/M3业务集成未验证。
- [D-02契约](../../contracts/d-master-data.md)：v0.1.0（proposed），调用真实HTTP适配；数据库只访问M1 schema。迁移：[001](migrations/001_reservations.sql)、[002](migrations/002_outbox_receipts.sql)、[003](migrations/003_suppressed_reminders.sql)，与幂等配置初值一起可重放，无手工业务改库。
- 独立 ASGI：`services.m1.main:app`；`GET /healthz`保留骨架响应，仅证明HTTP可响应。配置、启动、调度和测试说明见[README](README.md)。

## 验证与发布证据

- 编译、静态契约和diff检查通过。最终新建Docker PostgreSQL的 `scripts/test-business.py` 通过：D14项、M1 30项（25项真实数据库行为及5项无数据库适配边界，M1耗时16.104秒），含锁等待跨越签到截止、严格主数据校验、禁止重定向和过期提醒抑制，详见[验收记录](tasks/2026-10-22-backend-verification.md)。
- 该证据使用真实M1数据库与业务代码，测试替换D主数据响应并显式启用合成身份/模拟投递。不得据此宣称真实身份验证、D通知送达或M2/M3业务链路已通过。
- 同轮新建空库重放以及真实D-02↔M1 HTTP测试通过：CRUD、院系/本人范围、幂等、并发预约、多来源写回、schema权限隔离和提供方停止后的503。根 `bash scripts/check.sh` 已通过上述业务测试、两项关键行为变异检查、Vue 类型检查和构建；生产构建访客/只读预览浏览器回归也已通过。开发身份下的实际浏览器业务验收已通过：插座搜索→预约→取消→再次预约→取消；切换EE身份读取CS预约详情返回404并清空旧数据；学生访问D管理页由守卫转403；实际运营统计、M1来源及每日签到码显示正常，JavaScript错误0。运行[Playwright脚本](../../apps/web/tests/business.browser.cjs)时设置 `WEB_BUSINESS_TEST=1`，目标 `http://127.0.0.1:5173`，连接真实API和PostgreSQL并显式使用开发身份；详见[主任务](tasks/2026-10-22-completion.md)。这不构成真实D-01/03/04联调或部署证据。
- PR/提交、人工评审、部署环境、发布tag及远端迁移证据：待主任务登记或未验证。本机工作区修改不会自动同步到其他分支或环境。

## 依赖与待办

- D-01身份、D-03通知、D-04审计仍未实现/真实集成。消费请求为提案；完整[TEMPORARY-DEPENDENCY清单](temporary_dependencies/README.md)记录精确路径、配置、激活方式、责任组、替换触发、检查与保留代码。
- 正常模式仅使用真实HTTP，缺少配置/依赖失败返回503。开发双开关显式标注；SIMULATED和ACCEPTED不表示DELIVERED。
- Scheduler需要独立受监督进程；健康检查不证明调度器存活。实时通知中心/送达查询属D-03后续范围。
- 需由M1与M2/M3实际业务应用验证写回/恢复与来源，及D所属组完成人工契约/权限/迁移评审。Web端状态与验收见[前端状态](../../apps/web/src/modules/m1/STATUS.md)。

## 最近交接

- 2026-10-22：完成M1-01～08后端、版本化契约、PostgreSQL行为测试及临时依赖清单；见[后端验收](tasks/2026-10-22-backend-verification.md)。按需求提交和综合验收由主任务继续记录。
- 2026-10-22：初始骨架健康检查与拟议写回契约，已由本次实现状态取代；历史部署不代表新业务已发布。
