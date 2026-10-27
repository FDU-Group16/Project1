# M3 后端状态与交接

更新时间：2026-10-27。本记录对应 `m3` 分支首轮实现，基线 develop `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`。用户已授权技术复查通过后提交并上传 `m3`；精确提交与远端结果以 Git 记录为准，未合并到 develop，未部署，未登记队友业务验收。

## 本轮实现

- M3-01：`models.py`/`service.py`/`main.py` 实现故障上报、有效房间检查、操作者范围内幂等、派单/重派及权限/对象可见范围。
- M3-02：实现等待下架回执→维修中、乐观版本校验、SLA 自动升级、阶段去重；`worker.py` 自动扫描和持久化重试。升级只记录本地事件，D 通知未接入。
- M3-03：完工、验收拒绝返工、验收确认后关闭、一次性 1～5 星评价；开始维修后不能通过取消绕过验收。
- X-01/X-03/X-04 消费方：`m1_client.py` 用真实 HTTP PUT 写回稳定工单来源及版本，严格验证回执；`database.py`/`migrations/v0001.py` 事务写入工单/幂等/outbox，重启和 worker lease 恢复。只有 ACTIVE/RELEASED 回执确认后才完成对应状态切换。
- `dev_dependencies.py` 仅显式 development 模式使用合成身份/房间，M1 stub 还需 `M3_M1_MODE=stub`。正常/production 模式拒绝 demo，且不启动 worker 处理旧开发数据库。
- PostgreSQL 适配与 `m3` schema 迁移已编写；SQLite 只作显式本地开发/测试。不是 PostgreSQL 已验证或正式存储已部署的证据。

## 对外入口与契约

- 服务 `services.m3.main:app`；`GET /healthz` 保持原有 HTTP 健康语义，不代表业务依赖就绪。
- `/api/m3/v1/context` 返回实际运行/依赖模式；`/me`、`/rooms`、`/technicians` 及 `/work-orders` 查询和创建。
- 工单动作：assign/start/complete/accept/reject/cancel/rate/retry-sync。字段/错误以 [API 基线](../../contracts/m3-work-orders.md) 和 [OpenAPI](../../contracts/m3-work-orders.openapi.json) `0.1.0-proposed` 为准。
- M1 写回遵循原 [契约](../../contracts/m1-room-blocks.openapi.json) `0.1.0-proposed`，未修改提供方接口。M1/D 尚未实现真实依赖，不能宣称跨模块验收通过。
- 运行与恢复说明：[README](README.md)。前端由 [M3 Web 状态](../../apps/web/src/modules/m3/STATUS.md) 分别记录。

## 验证与发布证据

- 2026-10-26 `.venv/bin/python -m unittest discover -s services/m3/tests -v`：最终后端复核执行 42 项，41 通过，1 项真实 PostgreSQL 因无专用服务 URL 明确跳过。独立审查包含双 worker 租约接管、远端成功后本地 ACK 提交失败/重启恢复、并发扫描、连续 ACK 失败耗尽预算及正常模式隔离。
- 其中实际启动 Uvicorn：创建→派单→开始→后台确认→完工→验收→确认→评价通过；默认/production 使用 demo token 均被拒绝，未创建业务数据库。
- SQLite 实际文件持久化/空库迁移/重复迁移/重启恢复、并发创建与版本冲突、SLA 边界、暂时错误重试与永久错误停止已测试。
- M1 网络适配测试使用本机 HTTP 提供方替身，覆盖成功、超时、错误码、错误/过大/损坏回执、重定向；不代表真实 M1 可用或真实座位来源保留。独立审查发现并修复 RFC3339 校验、未知字段与损坏 HTTP body 三类缺陷，原回归断言通过；修复连续进程崩溃导致自动尝试预算可能被突破的问题，新增原断言通过。
- 根检查、浏览器及变异验证由本任务统筹在 [任务记录](docs/2026-10-26-implementation.md) 汇总。不得将未记录的命令预填通过。
- [2026-10-27 上传前复查](docs/2026-10-27-review-and-upload.md)记录最终检查、真实浏览器流程、独立复查及授权范围。无 PR/队友评审或测试/生产发布记录，无 PostgreSQL 真机及真实 M1/D 集成验收。

## 依赖、未完成与下一步

1. M3 两位同学评审角色、SLA、重派/返工、验收及自报自修限制；细化分批提交。拟议规则不表示全组达成一致。
2. M1 组提供真实 room-blocks API 和凭据；联合验证多维修工单、M2 占用及原 M1 预约限制不被错误清除，并确认永久错误的人工协调恢复流程。
3. D 组提供真实身份/资源授权/房间目录/维修人员目录以及通知与审计契约；默认拒绝业务的 `UnavailableDirectory` 待正式适配器替换。
4. 临时依赖清单及精确替换范围见 [任务](docs/2026-10-26-implementation.md#依赖替身清单)；`run-dev.sh` 同属临时启动入口。不能只删除替身而保留演示启动配置，更不能将其作为正式身份。
5. 真实 PostgreSQL、独立数据库账号、迁移在流水线执行、全模块测试部署、生产审批及回退仍待集成，不修改 M1/M2/D 代码代替其交付。

## 最近交接

- 2026-10-27：按用户明确授权完成上传前技术复查，后端 41 通过/1 跳过、前端 10 通过、全流程与改派撤权浏览器验收通过；仅提交推送 `m3`，不合并或部署。详见 [本轮记录](docs/2026-10-27-review-and-upload.md)。
- 2026-10-26：先建立范围/契约/验收方案，再实现 M3 可运行首轮；工作区同步、细化规则、临时依赖与未决事项见 [实施任务](docs/2026-10-26-implementation.md)。
