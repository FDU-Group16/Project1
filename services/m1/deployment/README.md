# M1 调度进程部署与运行监测

此处是部署准备和操作步骤，未替团队执行服务器发布。迁移与监测契约见 [v0.1.0-proposed](../../../contracts/m1-scheduler.md)，验证/集成边界见[任务记录](../tasks/2026-10-29-scheduler-monitoring.md)。

## 配置和启动

复用 API 镜像，独立执行 `python -m services.m1.scheduler`。无需安装 cron、Redis、Celery 或另建数据库。API 和调度器必须连接**同一个已初始化的 M1 schema**，使用现有独立 M1 账号；D 账号与 schema 不变。用既有 `scripts/provision-databases.py` 在受控环境初始化角色/schema，再由服务启动重放迁移；不要把管理员凭据交给运行进程。

- `M1_DATABASE_URL`：M1 账号的数据库连接串；Compose 内主机应为 `postgres`，不能使用宿主机回环地址。
- `APP_ENV=production`：Compose 中固定，正常配置不启用开发替身。
- `D_BASE_URL`、`D_NOTIFICATION_TOKEN`、`D_AUDIT_TOKEN`：真实通知/审计地址和独立凭据。缺失或投递失败只保留 PENDING 重试，不模拟接收；提供方缺口仍须相应组交付。
- `M1_SCHEDULER_ID`：实例标识，默认 hostname。Compose 单实例固定为 `m1-scheduler`；需要多实例时逐个设置不同 ID，不直接扩容相同固定 ID。
- `M1_SCHEDULER_STALE_SECONDS`：可选，默认 `max(90,3×轮询间隔)`；必须大于间隔且不超过 86400 秒。应覆盖正常最长周期及数据库/网络延迟，不能通过无限加大阈值隐藏卡住的进程。
- CLI `--interval` 默认 30 秒，`--batch-size` 默认每周期最多投递 20 条，`--failure-limit` 默认连续 3 次周期异常后退出。单次 HTTP 请求仍沿用 3 秒超时。大量预约扫描或锁等待也可能使周期超时，应结合积压与健康监测处理。

本机通用 Compose 默认仍可启动骨架；业务调度明确启用 profile：

```sh
docker compose --profile m1-business up -d --build m1-scheduler
docker compose --profile m1-business logs --tail 100 m1-scheduler
docker compose --profile m1-business exec -T m1-scheduler python -m services.m1.scheduler --healthcheck
```

`compose.staging.yaml` 将调度器作为必需服务，复用 `campus-resource-m1:${DEPLOY_SHA}`。发布前配置真实的服务数据库与投递依赖；新版本健康门槛会执行调度器本实例检查，缺少配置/迁移/成功周期时不会仅凭 API 存活宣布部署成功。`scripts/activate-staging.sh --check` 仍按原参数顺序使用：

```sh
bash scripts/activate-staging.sh "$DEPLOY_SHA" --check
```

运行脚本默认在 `~/campus-resource-staging`；`STAGING_DEPLOYMENT_ROOT` 可显式指定另一个发布根目录，用于隔离演练。旧发布未定义调度服务时仍可检查/回滚。Docker 镜像的现有 `restart: unless-stopped` 会在周期连续失败退出或进程崩溃后重启，正常 `SIGTERM` 会结束轮询等待、标记 STOPPED；若超过 30 秒停止宽限，容器可能被终止，持久化状态及事件 ID 支持后续重试。

## 监测与处置

`GET /api/v1/scheduler` 使用现有 D 身份，要求 `operations:read` 或 `room:manage`；管理凭据留在受控调用端，不放在公开页面或 shell 历史中。字段和状态的权威定义见契约。API 返回成功只表示完成了一次状态查询，须读取响应中的 status。

| 观测 | 意义与处理 |
| --- | --- |
| worker `starting` | 尚无成功周期；短暂启动正常，持续存在则检查依赖、锁等待和日志。 |
| worker `healthy` | 近期有完成周期，不能据此认为通知已送达。 |
| worker `error` / `stopped` / `stale` | 周期异常、明确停止或最后成功周期过期；检查进程/数据库，处理失败原因后恢复。 |
| overall `degraded` | 有健康实例，但存在失败待重试投递或未处理失约；检查提供方可达性、凭据、积压与处理能力。 |
| `healthyWorkers=0` | 应告警；即使 `/healthz` 返回 200，也不能认为自动业务正常。 |
| ACCEPTED / SIMULATED | 分别是提供方接收、开发模拟，不是渠道送达。 |

容器健康检查只查自己的实例，不会由其他健康 worker 掩盖。Docker 将心跳过期标为 unhealthy，**不会仅因 unhealthy 自动重启仍在运行的容器**；须由外部监控告警、监督系统或维护者诊断后重启。本轮提供可检测状态和发布门槛，未接入实际告警渠道。

心跳保存在 M1 自有表 `scheduler_workers`，不保存用户或事件载荷。API 仅显示最近 100 个实例，健康总数包含全部实例。实例重启清除先前成功心跳，旧进程无法覆盖新 run 的记录。`004_scheduler_workers.sql` 是增量迁移；回滚应用保留该表，禁止为回滚监测删除预约/发件箱数据。

## 验证

`bash scripts/check.sh` 默认创建一次性 Docker PostgreSQL。已有**明确可销毁的独立测试库**时，可显式设置 `TEST_M1_DATABASE_URL` / `TEST_D_DATABASE_URL` 后执行：

```sh
BUSINESS_TEST_EXTERNAL=1 bash scripts/check.sh
```

外部模式会清空测试 schema 的业务表，不能指向共享或线上数据库。`services/m1/tests/test_scheduler.py` 使用真实数据库与独立子进程测试无 HTTP 自动处理、双实例、重启去重、崩溃过期、鉴权/聚合、失败退出和缺迁移健康失败；`test_scheduler_deployment.py` 执行真实发布脚本，仅用 Docker/curl 边界夹具验证调度器失效会阻止健康通过，以及旧发布兼容性。
