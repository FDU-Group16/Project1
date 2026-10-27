# TEMPORARY-DEPENDENCY inventory

2026-10-27 annotation update; consumer M1, provider D. These substitutes cover only D-01 and D-03/D-04 responses needed to exercise M1. Actual D-02 always uses its network API. Scope and replacement approval remain in [task notes](../tasks/2026-10-22-completion.md).

| ID | Missing capability / assumption | Temporary paths and activation | Owners, replacement trigger and checks |
| --- | --- | --- | --- |
| M1-D-IDENTITY | D-01 trusted identity unavailable. Assumes `/api/v1/auth/me` returns id, nullable departmentId and permissions; proposed dependency contract in `contracts/d-dependencies.md` if present, and M1 public v0.1.0-proposed. Four synthetic bearer identities only, no account/password/session service. | `services/m1/temporary_dependencies/adapters.py::development_identity`; `M1_USE_DEV_DEPENDENCIES=1` AND `APP_ENV=development|test`. Tokens `dev-student-cs`, `dev-student-ee`, `dev-room-admin`, `dev-operator` are public synthetic test fixtures. | M1 integrating group + D-01 confirmed M2 owner. Replace after approved real identity endpoint and credentials exist; verify real identity, expired/revoked tokens, department filtering and resource authorization. |
| M1-D-DELIVERY | D-03/D-04 durable notification/audit provider unavailable. Assumes eventId deduplication, in-app notification request, `{eventId,status:accepted|delivered}` receipt. Accepted is not delivery evidence. | `services/m1/temporary_dependencies/adapters.py::development_deliver`; same dual activation; `M1_DEV_DELIVERY_FAIL=1` injects a retryable failure. Outbox stores SIMULATED and never DELIVERED for these calls. | M1 integrating group + D-03/D-04 confirmed M3 owner. Replace after approved endpoints; test real durable receipt, deduplication, bounded retry and actual channel delivery/audit retention. |

Development API responses expose `X-Dependency-Mode: development-substitutes`; reservations also include `dependencyMode`. The scheduler prints the mode. Normal runtime defaults to real HTTP and fails closed on missing credentials, malformed identity, provider errors or timeout. Setting the development flag outside allowed environments returns 503. No exception handler falls back to these adapters.

Cleanup scope after successful real integration: remove the two development functions and directory, the conditional imports in `dependencies.py`, `M1_USE_DEV_DEPENDENCIES` / `M1_DEV_DELIVERY_FAIL` development activation, synthetic identity tokens and fixture setup from runtime/demo documentation. Adapt (do not delete) lasting behavioral tests to inject a provider double with the real contract. Keep reservation/search/check-in/history/statistics logic, PostgreSQL migrations, scheduler, outbox, HTTP adapters, provenance, authorization/error handling and lasting behavioral tests. Run both real-provider integration checks and `bash scripts/check.sh` before documenting removal. These markers do not authorize deleting provider code or overriding working-tree changes.

## 显式开发启动器

`services/m1/temporary_dependencies/run_demo.py` 是同一消费方的临时启动配置：显式设置 APP_ENV=development、M1_USE_DEV_DEPENDENCIES=1、D_USE_DEV_IDENTITY=1 和 VITE_USE_DEV_IDENTITY=true，使用合成种子与本机 PostgreSQL；不会修改其他模块或启动生产部署。忽略文件 `.env.m1-development.json` 仅存本机随机凭据，数据库容器由脚本命名并持久保留。真实 D-01/03/04 接入后此启动器、上述开关与合成选择入口均在替换清单内；保留数据库迁移、标准服务/调度入口、真实适配和长期行为测试。

## 源码中的可修改边界

- `TEMPORARY-DEPENDENCY` 标出临时数据、开发接入分支及启动开关；M1 与提供组可在对应集成任务中协调修改或替换，真实联调通过后按上述清单清理。
- `CONTRACT-ASSUMPTION` 标出 `dependencies.py` 中真实身份/投递客户端的暂定路径与响应假设。M2（D-01）或 M3（D-03/D-04）与 M1 可协调调整接口映射，真实 HTTP、业务、鉴权、异常处理与长期行为测试仍需保留。
- `run_demo.py` 统一引用本清单的 `M1-D-IDENTITY`、`M1-D-DELIVERY`，以及 D/Web 清单的 `D02-IDENTITY`、`WEB-D01-IDENTITY`；不再另起别名。
- 本次只补注释，不变更提案契约或移除替身；范围和验证见[注释优化任务](../tasks/2026-10-27-temporary-interface-comments.md)。
