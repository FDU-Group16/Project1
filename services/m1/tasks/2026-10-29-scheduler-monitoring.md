# M1 调度器部署与运行监测

日期：2026-10-29。需求 M1-05、E-04/E-05/E-07/E-08。用户授权开发调度器部署与运行监测，不包含服务器发布。

## 范围和验收

允许修改 `services/m1/`、M1 监测契约及必要的 Compose 配置/测试入口。共享变更限新增 M1 调度服务、发布健康门槛、外部测试库开关及监测变异验证；同步需求追踪与数据最小化记录。不改 M2/M3/D 业务、身份或投递提供方。M1 负责实现集成，部署维护者和受影响组在合并前评审 Compose/契约/迁移，具体评审人员尚未指定。

方案：复用现有 API 镜像运行独立调度进程，使用 M1 自有数据库持久保存每个实例的最近成功周期、失败状态和心跳；管理接口提供实例健康与发件箱积压的聚合信息，容器使用本实例的健康检查。继续保留 `/healthz` 存活语义。正常模式不使用替身，不记录载荷、学生标识、令牌或原始异常。

验收：没有 HTTP 请求时独立进程自动处理到期预约；重启后不重复违约/事件；实例停机或周期失败能够识别；通知故障保留重试并在监测中报告；未初始化/数据库不可用不能健康；迁移可重复重放；监测接口需要管理权限。使用真实隔离 PostgreSQL 和子进程验证，不替换被测业务。现有 D 身份/通知/审计依赖保持原登记，本次不新增运行时替身。

## develop 核对

本任务涉及共享部署配置，触发 develop 获取。开始时分支 `m1`、HEAD `1b214d55ab8306c587cede0a725a5fac4383e1de`，工作区干净，无未完成合并；远程为既有 `origin`（https://github.com/FDU-Group16/Project1.git）。先登记本任务，再显式 fetch develop 成功，取得 `50ccf95f1fda292c907a3d1907f1c99f5b99f012`；命令后核对时间为北京时间 2026-10-29 00:09:17（UTC 2026-10-28T16:09:17）。分叉计数 m1/develop 为 1/4，HEAD 保持原提交，不进行自动合并/变基/摘取。

只读核对了该引用的根规则、Compose、D 提供登记及既有交接：develop 已有 M3 和临时账号配置，仍无独立 M1 调度服务；D-01/03/04 为 not_ready。已重读当前根规则、M1 状态/README、调度业务、迁移、任务模板和契约登记。当前 M1 独立开发不依赖 M3 新代码；根 Compose 改动限定 M1 数据库映射和新增调度服务。后续需人工将本次 M1 改动与 develop 的共享部署改动集成，不可用旧 m1 版 Compose 整份覆盖 develop；集成后重新检查配置和真实提供方。

## 验证与交接

- 代码：`scheduler.py` 新增实例注册、周期状态、可中断轮询、批量投递上限、健康命令和连续周期异常退出；既有预约/提醒/违约/发件箱行为保留。`monitoring.py` 与迁移 004 只访问 M1 schema，重启清除旧成功心跳，run ID 防止旧进程覆盖新记录；不输出原始异常或载荷。
- 入口：管理 API `GET /api/v1/scheduler`、容器本实例 `python -m services.m1.scheduler --healthcheck`，字段/权限以 [v0.1.0-proposed](../../../contracts/m1-scheduler.md) / [OpenAPI](../../../contracts/m1-scheduler.openapi.json) 为准。未改变 `/healthz` 语义。没有新增前端页面。
- 部署：本机 Compose 显式 profile `m1-business`，staging 调度服务必需；复用 M1 镜像/账号，默认不启用替身或公布端口。`activate-staging.sh` 的健康门槛新增实际 worker 检查，同时支持旧发布回滚；测试根目录通过 `STAGING_DEPLOYMENT_ROOT` 显式隔离。操作见[部署指南](../deployment/README.md)。Docker unhealthy 只提供检测，实际告警渠道/挂起进程的外部重启仍是运维集成工作。
- 环境：本机无 Docker。临时目录安装 [pgserver 0.1.4](https://pypi.org/project/pgserver/0.1.4/) 的 PostgreSQL 16.2 二进制及 YAML 检查工具，数据库仅监听权限受限临时目录内的 Unix socket；角色/schema 使用既有 provisioning 脚本隔离。未安装全局软件、未修改 Python/npm 锁文件或访问共享数据库。测试结束停止并移除每个临时数据库。
- 最终 `.venv/bin/python /private/tmp/project1-run-pg-checks.py` 在上述隔离库中执行 `BUSINESS_TEST_EXTERNAL=1 bash scripts/check.sh`，退出码 **0**：依赖登记 0 错误、24 项交接测试、27 个 OpenAPI 操作/引用、四服务 HTTP 健康、真实 M1↔D-02 HTTP 与 schema 隔离、D **14 项**、M1 **41 项**（含新监测 5 项、部署门槛 3 项）、3 项定向变异，以及 Vue 类型/生产构建均通过，无数据库测试跳过。日志 `/private/tmp/project1-scheduler-final-check.log`。
- 独立进程测试覆盖：无 HTTP 请求时自动失约；两个 worker 同时运行；SIGTERM 正常退出、同 ID 重启及事件/违约去重；SIGKILL 后健康过期且另一 worker 不掩盖；真实投递配置缺失时 PENDING 重试并显示 degraded；数据库表缺失后连续周期失败退出且日志脱敏；鉴权、聚合最小化及未迁移健康失败。
- 健康变异：故意将 worker 健康判断改为恒定 healthy，过期心跳测试出现断言失败；恢复后通过。现有院系/预约冲突两项变异也通过；没有保留错误实现。
- `python3 scripts/test-staging-images.py` **9 项通过**。Compose 用 YAML loader 检查合并键、镜像复用、账号映射、正常模式、无端口及健康命令；`bash -n`、`git diff --check` 通过。Docker Compose 实际容器构建/重启、PostgreSQL18、远端 CI 与服务器部署**未执行**。
- 已更新 M1 STATUS、监测契约、部署/配置说明及需求/伦理追踪。迁移是增量表，回滚旧应用应保留该表；不删除业务数据。D 身份/通知/审计及其清理库存保持原样，没有新增运行时替身。
- 人工评审、PR、合入 develop、推送与发布尚未执行；本轮验证对应 `1b214d5` 上的本地实现。共享部署文件与 schema 需维护者评审并在人工集成后重验。
