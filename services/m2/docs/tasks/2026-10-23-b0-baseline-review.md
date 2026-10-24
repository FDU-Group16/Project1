# B0：审批与超时共同基线评审

日期：2026-10-23（Asia/Shanghai）

角色：B（审批与超时处理）

状态：IN_PROGRESS（用户已授权代理完成技术自检后直接提交到 `m2`；尚未提交、未推送，不等同队友 PR Review）

## 协作需求与 develop 同步

- 触发原因：B 的后续实现依赖 A 维护的 M2-BASE、M1 写回契约和 D 身份/主数据能力，因此首次接入需确认公共工程基线与提供方状态。
- 实际工作区：`E:\Codex\M2project`。
- 工作分支：`m2`。首次准备时曾从 `origin/develop` 建立未上传的本地 `feat/m2-approvals`；用户于 2026-10-23 明确要求不使用新分支后，已将该本地分支重命名为 `m2`，远端未产生需撤回的 B 分支。
- 远程：`origin = https://github.com/FDU-Group16/Project1.git`。
- 获取远程 develop：2026-10-23，执行 `git fetch origin refs/heads/develop:refs/remotes/origin/develop` 成功。
- 工程基线与当前 HEAD：`99ce858a2bbf8caa2f4b226a83f989c54d6992d1`。
- 集成分支现状：`origin/m2 = a57193fd3e1ba5c411333b07ebb62b1419635fcb`，比上述 develop 少 13 个提交，不能作为当前开发起点。
- GitHub 只读检查：未发现远程 `feat/m2-approvals` 或 M2 相关 PR；提交前刷新发现 `origin/feat/m2-applications@3a0892119534df422f47ec1f0977c7b6462ed6c2`，该分支提供 A0-01 提案、公开/内部协议和基线文档，但没有 Base/UoW/模型/业务代码，且尚未合入 `m2`。
- 同步结果：本地 `m2` 直接基于已确认的 `origin/develop`；`origin/m2` 是该基线的祖先，落后 13 个提交。用户明确授权把本批放在 `m2` 后，本地仅采用分支重命名与后续非强制快进推送，不使用 merge commit、rebase、cherry-pick 或强推。
- 已重读：根与 Web `AGENTS.md`、需求基线、AI 任务模板、模块状态索引、M2/M1/D 后端状态、M2 前端状态、契约登记、M1 房间阻断 OpenAPI、ADR-0001/0002 和角色 B 任务书。

## 目标与范围

- 需求 ID：`M2-01`、`M2-02`、`M2-03`、`X-02`、`X-03`、`X-04`、`E-01`、`E-02`、`E-07`。
- 本批目标：完成 B0 首次事实核对，明确审批/超时提案、状态矩阵、接口依赖和可执行测试场景，为 A 的 M2-BASE 评审提供输入。
- 允许修改：
  - `services/m2/docs/automation/ROLE_B.md`
  - `services/m2/docs/tasks/2026-10-23-b0-baseline-review.md`
  - `services/m2/docs/decisions/0001-approval-expiry-policy.md`
  - `services/m2/docs/progress/B.md`
  - `services/m2/STATUS.md`
- 不在本批：业务代码、ORM/迁移、公开契约、M1/D/Web 公共层、依赖清单、测试数据库、worker、Git 提交/推送/PR。

## 当前事实与依赖结论

1. 仓库中的 M2 只有 `/healthz`，没有 M2-BASE、共同类型、UoW、业务路由、迁移或测试。
2. A 的远程分支已出现：`origin/feat/m2-applications@3a0892119534df422f47ec1f0977c7b6462ed6c2`。只读核对表明其 A0-01 仍是提案/接口准备，没有共同 Base/UoW/模型实现，也没有已合入 `m2` 的 M2-BASE SHA。
3. `contracts/m1-room-blocks.openapi.json` 是 `0.1.0-proposed`，M1 提供方尚未实现；D 的身份、权限、房间主数据、通知和审计契约也未定稿、未实现。
4. 根规则把分支约定标为 proposed；用户已明确选择本批直接提交到 `m2`，因此不创建 B 个人分支或到 `m2` 的 PR。后续 `m2 → develop` 仍须团队评审和人工合入，本批不创建该 PR、不合并 develop。
5. B1 依赖共同 Base/UoW、状态类型和端口签名，当前不得自行复制一套正式基础。可继续的工作仅限 B0 方案、矩阵和测试设计。

## 方案

采用“先锁定政策提案和接口验收，再接入 A 的单一基础”的方案：

1. 将审批与超时规则以 `Proposed` 决策记录表达，不冒充团队结论。
2. 用下列矩阵约束 B1～B4 的可观察行为；所有写状态操作必须经 A 的 `ApplicationPort`，并复用 A 的 UoW 和资源命令仓储。
3. A 的基础可读取后，先核对签名、事务责任、状态枚举和迁移 parent，再建立审批模型；任何不匹配先提案，不在 B 分支复制共同定义。

## 审批与超时状态矩阵（待团队确认）

| 当前状态 | 事件/前置 | 目标与 B 侧动作 | 必须保持的不变量 |
| --- | --- | --- | --- |
| `PENDING_LEVEL_1` | 合法一级通过，未截止 | `PENDING_LEVEL_2`；完成一级任务和记录，创建唯一二级任务 | 禁止自批、越权、重复处理；一级通过不批准申请 |
| 两种 `PENDING` | 合法驳回或申请人撤回 | `REJECTED` / `WITHDRAWN`；关闭待办并记录原因 | 从未发过 ACTIVE，或此前 ACTIVE 已由更高 RELEASED 清理 |
| 两种 `PENDING` | `now >= deadline_at` | `EXPIRED`；关闭待办并写系统事实 | 申请状态与待办同事务 |
| `PENDING_LEVEL_2` | 合法最终通过，未截止 | `RESOURCE_PENDING`；同事务落盘审批意图与 ACTIVE 命令 | 提交事务后才调用 M1，不持锁等待网络 |
| `RESOURCE_PENDING` | 当前 ACTIVE 匹配成功，确认时仍未截止 | `APPROVED`；二级任务 `PASSED`，写唯一最终通过记录 | 回执未被更高命令替代，审批人仍是原审批人 |
| `RESOURCE_PENDING` | ACTIVE 返回占用冲突 | 保持处理中，建立更高 RELEASED；恢复目标 `PENDING_LEVEL_2` | 未确认释放前不得回待审或写最终通过 |
| `RESOURCE_PENDING` | 到达截止 | 建立或复用更高 RELEASED；恢复目标提升为 `EXPIRED` | 不再重试旧 ACTIVE；重复扫描不新增 revision |
| RELEASED 在途 | 到达截止 | 复用同一 RELEASED，仅提升本地恢复目标 | 不降回待审，不更改已落盘请求载荷 |
| 当前 RELEASED | 匹配成功且已截止 | `EXPIRED`；关闭待办，终结原批准操作 | 先确认清理，再结束业务 |
| 当前 RELEASED | 匹配成功、未截止且目标待审 | `PENDING_LEVEL_2`；原批准操作以资源冲突结束 | 新逻辑审批必须使用新幂等键和新版本 |
| 任意终态/被替代命令 | 迟到旧回执 | 忽略或记录一致性故障，不改变业务终态 | 旧 ACTIVE 不能覆盖 RELEASED、过期或终态 |

## 对 M2-BASE 的评审清单

- 唯一 Base/Session/UoW；port 不独立 commit/rollback，顶层用例提交。
- 共同 `ApplicationStatus`、`Actor`、`ApplicationView`、`ApprovalProgress`、`RoomBlockCommand/Result` 与错误分类。
- `ApprovalPort.initialize/close_pending/progress` 与 `ApplicationPort.get/transition` 的准确签名及事务边界。
- `ResourceCommandStore` 的持久化 revision、同 operation+目标幂等、claim/租约/结果保存/重试接口。
- 状态迁移集中且条件更新可表达审批、撤回、过期和资源回执竞争。
- 正式装配不会静默回退测试替身；外部依赖模式显式可见。

上述项目当前均是待 A 实现和双方评审的要求，不是仓库已有能力。

## 独立测试场景设计

在共同基础尚未到位时只设计、不伪造通过结果：

1. 一级初始化重复调用只产生一个待办；初始化失败使申请与幂等意图整体回滚。
2. 一级通过不能直接批准；同一申请不能跳级、重复审批或由申请人自批。
3. 院系/房间管理范围分别覆盖允许、越权、空范围和全局范围，分页前先授权过滤。
4. 驳回、撤回、普通待审超时与关闭待办同事务，故意让关闭失败时状态不部分提交。
5. `now == deadline_at` 按过期处理；审批与超时竞争只有一个合法胜者。
6. 最终批准的原幂等键重放返回原结果；同键不同输入冲突；申请 version 与 M1 revision 分离。
7. M1 已应用 ACTIVE 但响应丢失、M1 成功后本地落库失败，重启后用同一命令恢复并保留原审批人和意见。
8. ACTIVE/RELEASED 回执乱序、释放响应丢失、重复扫描和多 worker claim 不产生状态倒退或无限 revision。
9. 三种 409（占用冲突、旧 revision、同 revision 载荷不符）采取不同处理。
10. 使用真实 A/B 与 PostgreSQL 的组合测试在 M2-BASE 和隔离数据库可用后执行；M1/D 可用替身仅验证消费方编排，不能作为 G5 通过证据。

## 临时依赖

本批不使用替身。后续若需要，须先按根规则登记稳定依赖 ID、显式启用方式、可替换文件和真实联调触发条件。

## 验收条件与证据

- 事实、SHA、分支、远程和提供方能力与 Git/GitHub 只读检查一致。
- 提案明确标为未批准，未把 M1/D 契约或 M2-BASE 写成已实现。
- 状态矩阵涵盖两级审批、截止、占用冲突、清理、迟到回执和幂等边界。
- 本批实际差异只包含“允许修改”中的文件。
- 验证：`git diff --check`、Markdown 链接目标检查、完整 tracked/untracked 差异复核；不运行数据库、worker 或业务测试。

## 待人工/团队决定

1. 是否批准两级审批、禁止自批、院系/房间管理范围和截止公式。
2. 是否批准“待审不占用、最终审批经 M1 确认后批准、占用冲突先清理再回待审”的政策。
3. A 的同步/异步技术风格、准确端口签名、命令仓储 claim/租约接口与唯一迁移链。
4. 团队确认 `m2 → develop` 的评审、合入负责人和时机；A0-01 尚在 A 的个人远程分支，需由团队决定如何评审并接入 `m2`，B 不代为合并。
