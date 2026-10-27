# 临时依赖发现与集成交接

提供方完成接口后，用一个命令查出哪些消费方仍待接入；消费方通过真实联调并清理替身后，才关闭自己的依赖记录。记录随 Git 提交共享，检查只反映当前检出的版本。

```bash
# 查看当前所有临时依赖及下一步
python3 scripts/check-dependencies.py

# M2 完成身份能力后，查所有 D-01 消费方
python3 scripts/check-dependencies.py --provider D-01

# M3 查自己提供的通知、审计能力影响哪些消费方
python3 scripts/check-dependencies.py --provider-owner M3

# 某项集成任务验收：选定范围必须全部完成
python3 scripts/check-dependencies.py --provider D-01 --require-complete

# 机器可读报告；也可按 --consumer M1 筛选
python3 scripts/check-dependencies.py --provider D-01 --json
```

`--require-complete` 必须显式选择 provider、provider-owner 或 consumer，零匹配不能算通过。多个筛选条件取交集。所有结构和源码标记检查始终覆盖全仓，筛选只限制报告及完成验收范围。

## 两方分别登记，汇总自动生成

| 记录 | 放置与维护方 | 内容 |
| --- | --- | --- |
| `PROVIDES.json` | 提供服务目录；当前在 [D](../services/d/PROVIDES.json)，由各 D 子域负责组维护对应条目 | 能力 ID、负责组、是否可开始联调、实现版本与证据 |
| `DEPENDENCIES.json` | 消费者自身目录；当前 [M1](../services/m1/DEPENDENCIES.json)、[D-02](../services/d/DEPENDENCIES.json)、[公共身份](../apps/web/src/shared/auth/DEPENDENCIES.json) | 依赖 ID、消费者、提供能力、接入进度、源码标记位置、验收证据 |
| 详细临时清单 | 原有模块 README/任务文档，通过 `inventory` 引用 | 激活方式、临时假设、替换路径、保留业务和验收步骤 |
| 模块 `STATUS.md` | 各模块分别维护 | 人可阅读的实现、验证和部署边界，链接上述记录 |

工具自动发现 `services/*/PROVIDES.json`，以及 `services/*/DEPENDENCIES.json`、`apps/web/src/modules/*/DEPENDENCIES.json`、`apps/web/src/shared/*/DEPENDENCIES.json`。不要求各组修改一张共享进度表；[模块索引](module-status.md)保持稳定入口。

一个消费者可以依赖多个能力，例如 `M1-D-DELIVERY` 同时依赖 D-03 与 D-04。一个临时文件也可被多个记录引用，例如演示启动器同时启用后端和 Web 的临时身份。

## 提供方完成时

1. 按根规则核对并同步 develop，确认当前提供方代码和契约；未合入的其他分支代码不会被此报告自动发现。
2. 更新自己的 `PROVIDES.json` 条目、STATUS 与验证记录：接口具备联调条件时改为 `integration_ready`，填写被测实现的完整提交号、契约路径/版本/评审状态和证据路径。不要仅因有接口提案或健康检查就声明可联调。
3. 运行 `--provider <能力 ID>` 或 `--provider-owner <组>`，把报告中每个未完成消费者的依赖 ID、负责组、下一步放入本次任务/PR 的交接内容；由双方安排有明确路径范围的集成任务。无需直接修改别组的记录。
4. 提供方可先合并。现有 CI 会打印消费者尚未接入的提示，不因并行开发中的正常待办阻断提供方提交。

`not_ready` 表示本检出尚未登记可联调的实现；`integration_ready` 表示指定版本已由提供方登记为可开始联调，不代表消费方已验收、接口提案获批或已部署。

## 消费方接入与关闭

| 消费方状态 | 含义 | 下一步 |
| --- | --- | --- |
| `temporary` | 使用开发替身支撑验证，真实提供方联调未完成 | 等待提供方或安排接入；不表示生产在运行替身 |
| `integrating` | 已安排接入并正在协调/验证 | 按详细清单完成真实接口验收 |
| `verified` | 已登记指定版本的真实联调证据，临时内容尚待清理 | 清理清单范围中的替身及激活配置，保留消费者业务和真实客户端 |
| `cleaned` | 真实验收与清理完成，保留记录供追踪 | 运行选定范围的 `--require-complete`，归档交接 |

`verified` / `cleaned` 必须记录真实验证所针对的消费实现提交、各提供能力实现提交、环境、命令及证据文件。提交号应指已验证的代码版本，不要求包含当前记录的提交引用自己的 SHA。若提供方后来登记了新实现版本，或将就绪状态撤回为 `not_ready`，工具提示 `reverify`，不会自动抹掉旧证据，也不会假定兼容性；双方确认后更新验收记录。

替身路径移除时同步更新 `marker_paths`；已 `cleaned` 的记录可以保留历史路径。共用文件按 ID 和清单中的函数/分支范围协调清理，不能删除整份真实客户端、其他依赖的替身或原有数据库。

## 记录格式

两种 JSON 文件均使用 `schema_version: 1`；字段以仓库内实际记录为样例。

- 提供记录的 `capabilities[]`：`id`、`owner`、`status`、`status_file`、`contract`、`implementation`。其中 `contract` 有 `path/version/status`（`proposed` 或 `approved`）；`implementation` 在 `not_ready` 时可为 null，联调就绪时必须有 `revision`（40 位 Git SHA）和 `evidence`（仓库相对文件路径）。
- 消费记录头：`consumer`、`owner`、`status_file`、`dependencies[]`。每项有 `id/providers/status/inventory/contract/marker_paths/verification`。状态和源码位置由消费方维护。
- `verification` 未验收时为 null；验收后有 `consumer_revision`、`provider_revisions`（每个能力 ID 对应一个 40 位 SHA）、`environment`、`command` 和 `evidence`。无真实证据时不得填写假值来通过检查。
- 所有路径均相对仓库根目录，不能越界；证据、状态和契约文件必须存在。记录中不保存凭据或真实个人数据。

正常修改能力契约时，分别更新提供方契约记录及受影响消费者的假设；脚本不会替代字段兼容性评审。一个依赖引用多项能力时，需要分别记录全部提供方版本。

## CI 检查与可见范围

`bash scripts/check.sh` 会先运行依赖检查及其行为测试；既有 CI 和 develop 测试部署工作流都会经过这个入口。

- 扫描 `services`、`apps/web/src` 的 Python/TypeScript/JavaScript/Vue 源码和 `apps/web/.env.example`。标记后跟稳定 ID；同一行多个 ID 用 `/` 或英文逗号 `,` 分隔，例如 `TEMPORARY-DEPENDENCY M1-D-IDENTITY / M1-D-DELIVERY: 说明`，中英文冒号后为说明。排除文档历史、工作树、依赖/缓存和真实 `.env`。
- 新 `TEMPORARY-DEPENDENCY` 未登记、登记路径与标记不一致、未知能力/ID、重复记录、错误状态或缺少证据都会失败。`cleaned` 仍残留同 ID 的 TEMP 标记也会失败。
- `CONTRACT-ASSUMPTION` 可以随真实客户端保留；它不会被误判为需要删除的替身，ID 仍应能定位登记。
- 提供方已就绪而消费者仍待接入时，输出明确待办；GitHub Actions 文本模式可显示 warning。`verified` 提示清理，版本变更提示复核；只有对应版本验收且已清理才是 `complete`。
- 默认检查允许已登记的未完成依赖。针对某个集成任务使用 `--require-complete` 才要求选中范围全部完成；退出码 0 为通过，1 为记录错误或严格验收未完成，2 为无效/无匹配选择。

工具读取登记和源码，**不会自行判断接口是否真实可用、验证报告是否可信，或发现未登记的外部完成情况**。提供方仍须在交付时更新记录；评审和真实网络验收仍须执行。它不发送飞书/邮件、不创建待办、不自动修改记录或删除代码。运行前按协作规则取得最新 develop 后，报告才代表该版本的集成状态。
