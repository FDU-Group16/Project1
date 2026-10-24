# M2 开发任务书 B：审批与超时处理

> **2026-10-23 分支执行覆盖说明**：用户最新明确要求“不新开分支，将文件部署在 `m2` 分支下”。因此，本文件中要求 B 使用 `feat/m2-approvals`、把 `m2` 仅视为候选 PR 目标或禁止更新 `m2` 的旧说明，在本仓库本角色后续执行中均由该明确指令取代。固定工作分支与推送目标均为 `m2`，上传命令使用 `git push --no-follow-tags origin HEAD:refs/heads/m2`；不创建 B 个人功能分支，也不创建“B 分支到 m2”的 PR。进入 `develop` 仍须团队评审和人工合入，禁止自动合并或发布。

**使用人：队友（B）。请把本文件完整交给自己的 Codex。**

**开始方法：附上本文件，再发送下面这一句话，无需填写技术字段或另行复制长段指令。**

> 请按附上的任务书执行，完成首次检查，并按第11节创建定时开发任务；每批做好后给我验收，再按约定上传。

执行助手收到用户这句明确请求后，按本文件第11.2节的完整流程执行；不要求用户重复粘贴同一流程。用户只发送附件或要求阅读、解释、审查时，不据附件里的示例自行启动开发或创建自动化。文件中写有计划不代表计划已经创建，以工具结果为准。

两人各自在自己的 Codex 聊天使用对应文件，不在同一工作区同时运行两份任务。首次结果应说明实际目录、个人分支、当前完成或阻塞的任务，以及定时任务是否已创建成功；缺登录或运行条件时只说明实际缺项，不虚报成功。以后在这个聊天续做，不必每天重发任务书。每批完成后查看成果和测试，再用第12.2节的文本授权上传；PR仍由队友评审、由人合入。读取 GitHub 进度和接口由 Codex 处理，本地分叉等需要人工接入时由它给出具体方案。定时运行需要保持机器与应用可用，创建后核对至少一次实际触发结果。

这是可独立使用的完整任务书，包含当前仓库基础、共同接口、个人任务、测试、GitHub协作和定时开发。共同章节在两份文件中完全一致。完成B0的契约评审；基线未到位先做场景设计，随后用真实A代码完成B1。

本文件适用于已有Project1工程。使用上面一句启动请求即可，第11.2节保留完整执行细节：个人分支已填好，本机开发路径由Codex定位；尚未下载仓库时按第11节建立专用克隆。PR目标先核对团队约定，不要求用户预填技术字段。计划已写为每天10:00、14:00、17:00开发，09:00—18:00内发起上传，时区Asia/Shanghai。只开发一次可用第12节。定时开发可以自动推进到待验收批次，本人验收授权后Codex才能在窗口内代为上传，合入develop后由既有流水线部署。

首次保存文件及每轮续做前须通过第3.4节的工作区、分支和文件范围检查；其他模块只读，公共文件需具体共享任务。Git上传遵守第7节的精确目标和完整差异检查，测试与worker遵守第9节的环境隔离要求。

## 1. 目标、事实基线与执行边界

你是校园资源服务平台 M2 的开发助手。目标是在已有 Project1 工程中，由两人分别实现申请与资源对接、审批与超时处理，最终通过真实网络接口接入 M1 和 D，并留下可核对的需求、设计、代码、测试、人工评审和部署记录。

目标仓库：https://github.com/FDU-Group16/Project1 。本文核对日期为 2026-10-22，核对的 `develop` 为 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`，当时远程 `m2` 仍为初始提交 `a57193fd3e1ba5c411333b07ebb62b1419635fcb`，落后该 `develop` 13 个提交。这些是编写时的事实；执行时必须核对实际远程与本地状态，不固定回退到这些 SHA。

### 1.1 已有能力与待完成事项

| 范围 | 编写时实际情况 | 本任务的处理 |
|---|---|---|
| 后端 | `services/m1`、`m2`、`m3`、`d` 四个独立 FastAPI 服务，只有 `/healthz` | 复用 M2 入口 `services.m2.main:app`，添加业务路由 |
| 前端 | `apps/web` 一个 Vue 应用，已有公共布局、首页和登录入口，以及 M1 浏览与只读示例预览；M2/M3 仍为静态说明页，尚无真实身份或业务 API 接入 | 在 `src/modules/m2/` 增加页面，复用公共界面，不重建应用；示例数据不作业务联调证据 |
| 数据 | PostgreSQL 18 已配置；尚无业务表、服务隔离账号和迁移体系 | 先确定 M2 数据边界和迁移方案，再建立真实表 |
| M1 写回 | `contracts/m1-room-blocks.openapi.json`，`0.1.0-proposed`，未实现 | 先共同评审协议，A 实现消费适配，真实联调待提供方就绪 |
| D | 只有健康检查，无已定稿身份、主数据、通知和审计业务接口 | 记录依赖；隔离替身可用于测试，不当正式服务 |
| 流水线 | 统一检查、PR CI、develop 测试环境部署已建立且有成功运行 | 小范围接入 M2 测试、迁移和 worker，不重写整个部署体系 |
| 线上 | `https://pj1.756888.xyz/m2` 为静态说明页 | 页面存在不代表申请或审批可用 |

### 1.2 开发前必读

读取根 `AGENTS.md`、`apps/web/AGENTS.md`、实际存在的 M2 局部 `AGENTS.md`、`docs/requirements.md`、`docs/ai-task-template.md`、`docs/module-status.md`、`services/m2/STATUS.md`、`apps/web/src/modules/m2/STATUS.md`。涉及 M1/D 时，读取提供方 STATUS、`contracts/README.md`、对应 OpenAPI 与 `docs/decisions/`；涉及公共前端时再读 `apps/web/STATUS.md`。每批 `services/m2/docs/tasks/` 中的任务沿用现有 AI 任务模板，填写需求、范围、验收、影响与验证。

课程原始文件为仓库 `任务书.pdf`，不得修改或删除。需求文档、接口提案、代码实现、测试成功、人工批准、部署成功是不同事实。`proposed` 不代表已获团队同意。

用户明确要求按本任务书执行时，Codex 才开展范围内的代码、测试、文档与仓库检查；仅交附件或要求阅读、解释、审查，不视作执行或创建自动化的授权。每批 AI 变更先提供可审查结果，由本人验收后才提交推送；PR 由队友评审，合并冲突由人处理。这来自课程过程要求及仓库规则。当前编写这两份文档本身不创建自动化、不执行开发、不上传 GitHub。

存在冲突时，列出具体规则、影响及可选方案，继续不受影响的工作；不能擅自把提案改成团队决定。不要制造空提交、倒填日期、假评审、假故障或假测试来凑过程记录。

## 2. 需求与先行决策

### 2.1 与仓库一致的需求编号

| 需求 | 本模块必须交付的行为 | 主责 |
|---|---|---|
| M2-01 | 后端校验申请资格、审批权限及管理范围 | A 身份适配与申请校验；B 审批校验 |
| M2-02 | 整室申请、查询、多级通过或驳回及处理记录 | A 申请；B 审批 |
| M2-03 | 到约定截止时间自动撤销未完成的申请 | B 作业；A 提供资源命令能力 |
| X-02 | 最终批准后 M1 对应整室时段不可个人预约；驳回/超时无本申请残留占用 | A 网络适配；B 编排；M1 提供者参与 |
| X-03、X-04 | 来源追溯，只释放本来源，通过公开网络接口集成 | A/B 与 M1/M3 联调 |
| D-01～D-04 | 接入已确认的身份、房间主数据、通知和审计 | 按公共契约消费；不默认认领 D 的实现 |
| E-01～E-09 | 任务范围与验收、版本化迁移、有效测试、评审、部署与真实过程 | 两人按职责维护 |

可增加细分任务 ID，例如 `M2-A1`、`M2-B2`，但每项必须关联上表主需求，不另建无法追溯的编号体系。自然语言业务代理为附加项，主功能完成后再另行安排。

### 2.2 首批需要确认的业务方案

下面是供两人和受影响模块评审的完整开发建议，尚非课程指定参数或团队已批准规则。先写入 `services/m2/docs/decisions/`，记录实际决定人、日期、理由和范围；影响共享政策的结论同时关联全组 ADR/契约。未确认时可完成需求拆分、接口草案、测试设计和无争议基础能力；受争议行为不进入正式业务实现或发布。

| 项目 | 建议方案 | 需要谁参与确认 |
|---|---|---|
| 申请资格 | 可信身份具有 `m2.apply` 且满足房间开放范围 | M2 与 D 身份/主数据负责人 |
| 审批 | 固定两级，一级按申请人院系、二级按房间管理范围；禁止自批 | M2 与 D 权限负责人 |
| 占用时点 | 待审批不占用，最终审批需 M1 成功确认后才算批准 | M2、M1 |
| 个人预约冲突 | 不挤占已有个人预约，返回占用冲突并允许处理后再次审批 | M2、M1；维修冲突涉及 M3 |
| 撤回 | 申请人仅可撤回两种待审批状态；批准后的取消不在首期范围 | M2 |
| 截止 | `min(提交时间+24小时, 使用开始前30分钟)`；相等时算过期 | M2；参数可配置 |
| 扫描 | 60 秒检查一次，单独受管理 worker，支持重复与并发执行 | M2 与部署维护者 |
| 恢复 | 以更高版本 RELEASED 确认清理，再过期或回到二级待审 | M2、M1；详见第 4 节 |

最终确认不同方案时，先在两份任务书共同基线及实际契约中统一变更，再实现，不允许 A/B 各用一套规则。

### 2.3 技术事实与候选实现

已有：Python 3.12、FastAPI、Uvicorn、Pydantic（FastAPI 依赖）、PostgreSQL 18；Node.js 24、Vue 3、TypeScript、Vite、Vue Router；后端根 `pyproject.toml`/`uv.lock`，前端 `apps/web/package.json`/`package-lock.json`。

当前没有 SQLAlchemy、Alembic、pytest、Axios、Element Plus 或状态管理库。M2 数据实现建议选同步 SQLAlchemy 2.x、PostgreSQL 驱动、Alembic 与 pytest，但要按实际团队决定安装、测试并锁定。A0 统一确认同步/异步风格，B 不另选。前端可使用公共 fetch 封装；Axios 和 UI 库不是必装条件。新增依赖必须有用途，沿用已有依赖清单与锁文件，不另建一套根工程。

ADR 0002 仍为提案：M1 组承担房间/座位主数据，M2 组承担身份/RBAC、共享登录与首个 HTTP 鉴权接入，并协调首次 D 集成，M3 组承担通知/审计。本任务书不把该提议当已分配任务。若组内采纳，另列 D/公共层子任务、人员、目录和验收，由受影响组评审。M2 的 Actor 适配器不等于 D 的身份系统，已有登录入口页面也不代表鉴权已实现。

### 2.4 首次启动的工具链与机器条件

首次运行及更换运行环境时，先只读核对实际可执行文件、版本和路径，再安装或执行项目命令。后端 `requires-python` 为 `>=3.12,<3.13`，`.python-version` 为 3.12；现有 CI 使用 Python 3.12、Node.js 24 和 `uv==0.10.0`。Node.js 24 是已核对的 CI 基线，不把它误写为当前 `package.json` 已声明的 engines 限制。系统默认 Python/Node 不一定满足项目要求，不能只凭命令存在就继续。

1. 检查 Git、Python、Node、npm、uv 的实际路径与版本；需要数据库测试时再检查 PostgreSQL 或容器工具及其目标。缺工具分别记录，不把尚不需要的 Docker/psql 缺失视为文档或纯逻辑工作的阻塞。
2. 优先使用机器已装的兼容运行时，包括 Codex 提供的 Python 3.12 和 Node.js 24。若只缺 uv，可在仓库跟踪目录之外建立本任务独立工具环境，安装与 CI 一致的 `uv==0.10.0`，通过本进程专用 PATH 或明确可执行文件路径运行；不得升级系统全局 Python/Node、修改全局 PATH 或为迁就机器环境改项目依赖/锁文件。工具安装或依赖安装前仍须通过第3.4节，核对下载、缓存及文件写入目标。
3. 使用已核对的 Python 3.12 建立项目环境，使用匹配 Node.js 24 的 npm，执行现有锁定安装。安装后检查 Git 差异，确认 `pyproject.toml`、`uv.lock`、`package.json`、`package-lock.json` 未被非授权改动。已验证可行的策略是兼容运行时加独立 uv 工具环境，不要求队友机器具有相同绝对路径。
4. 检查本人 Git `user.name`、`user.email` 是否已配置及是否正确；缺失仅阻塞提交，不阻塞只读核对、允许范围内的本地实现和验证。不得猜测身份或修改 Git 全局配置。`gh` 是否安装与 Git 是否具有推送认证是两件事；缺 `gh` 不等于不能使用 Git，能公开读取/克隆仓库也不证明有写权限。推送与 PR 能力在实际需要且已获授权时分别核验，未验证就明确标记。
5. 把实际解析到的 Python、Node、npm、uv 绝对路径、必要的本进程 PATH、项目环境路径及验证结果保存到本角色不入库的本地运行记录。保存定时任务时引用真实路径和所需环境，并要求每次启动重新核对路径与版本；不能依赖当前终端激活状态或写入仅适用于另一台电脑的路径。记录中不保存令牌、密码或其他凭据。

## 3. 分支起点、目录和共同基础

### 3.1 首次接入与后续同步

1. 由 Codex 按第 11 节先定位本角色的 Project1 开发工作区，不要求用户预先填写绝对路径。优先核对当前聊天关联的项目和当前目录，校验 origin 确实指向 FDU-Group16/Project1，再检查当前分支、HEAD、未提交文件、冲突、未完成 merge/rebase 和活跃任务。本文的审查副本路径不能当成两人的开发路径，也不能自动选用临时审查克隆。
2. 首次接入需要复用全组工程和 M1/D 契约，按根规则读取最新 develop：`git fetch origin refs/heads/develop:refs/remotes/origin/develop`，记录时间、远程和 SHA。网络失败则注明最新状态未确认，不能把本地旧内容当最新远端事实。
3. 两人从同一个确认的工程基线开始。仅在当前分支准确等于本角色个人功能分支、暂存区与已跟踪文件干净、未跟踪文件不会被覆盖且无并发写入时，按根规则允许 `git merge --ff-only origin/develop`。新个人分支可以从已确认的起点建立。不得移动本地或远程的 m1、m2、m3、d、develop、main、发布分支或其他人的个人分支；detached HEAD 上不写代码、不移动基线。
4. 远程 m2 尚未包含 develop 时，由集成人先准备并评审基线同步的 PR/操作；不能为“方便”自动推送 m2/develop。若直接把包含全组骨架的个人分支 PR 到旧 m2，会混入大量非本人改动，应先解决集成分支基线。
5. 分支分叉、有未知改动或未完成 Git 操作时，保留现场并交人处理。不得自动 stash、reset、rebase、cherry-pick、制造合并提交或处理冲突。
6. 同步后重读实际规则、状态和契约，验证真正检出的代码。只用 `git show origin/develop:...` 阅读远程文件，不能写成“本地已经集成”。

建议流程为个人功能分支 → 队友评审到 m2 → 全组评审到 develop → 自动测试部署；但根规则把分支约定标为 proposed，A0 须记录团队最终选择及各 PR 的真实 base。也可采用团队已确认的其他流程，不能各自猜测。PR 目标就是“本次代码经评审后准备合入的分支”；`m2` 是本任务书的候选目标，分支存在不等于团队已确认此流程。Codex 先查仓库规则及已记录的团队决定，仍无法确定时再说明候选方案，请用户向组内确认。该决定未完成不妨碍独立本地任务和计划设置，但不能据此自行创建目标未确认的 PR 或移动集成分支。

本任务书已填好 A/B 默认个人分支，分别为 `feat/m2-applications`、`feat/m2-approvals`。在本角色专用 checkout 中核对本地和远端同名分支；两边都不存在才从确认的工程基线创建，远端已有且归属已确认则检出并跟踪该分支，已存在的工作先核对后续做。无法确认归属时不擅自占用或改名绕过，不能 reset、删除或覆盖同名分支。两人不共写同一工作区。

后续纯 M2 任务不要求每轮 fetch develop。只有实际需要其他模块或 D/公共配置时才触发根规则中的 develop 同步；依赖对方已合入的 M2 代码时，读取约定集成分支，安全快进遵守实际规则，分叉由人处理。对方代码已合入公共分支，不代表已进入本人的本地工作区：本地已有提交导致分叉、存在未提交批次，或当前规则未授权该来源的同步时，Codex 先只读核对双方历史，给出保留现有工作的具体接入方案及需要人工完成的步骤，不能自动 merge/rebase/cherry-pick 或覆盖文件。待人工接入完成后重新验证，再继续依赖该基础的任务。

### 3.2 M2-BASE 的责任

A 是 **M2 内部共同定义与装配** 的主维护者，B 是审批接口和事务边界的评审者。A0 分成可审查的小批次：先定方案和签名，再落实 M2 模型基础、事务和装配。不新建全组 FastAPI/Vue 应用或部署系统。

首批共同基础应可独立导入、检查和评审，不能要求 B 的完整审批功能先完成才交付。A 完成本批范围内的验证后即可提请本人验收上传，将尚未进行的 A/B 组合明确标记为 BLOCKED；B 同样可先交付独立可验证的准备或接口实现批次，不能把最终组合验收误当成所有早期批次的上传前提。正式装配只注册实际可用实现，不靠导入尚不存在的对方文件或静默替身掩盖缺口。

M2-BASE 应包含：实际路径、M2 唯一 Base/Session 或等效事务工厂、共同状态与类型、ApplicationPort/ApprovalPort/RoomBlockPort、唯一迁移链、模型注册、正式依赖注入、必要检查命令，以及 `services/m2/docs/baseline.md`。只在 M2 服务内共享 Base 和事务，不跨四个服务共享业务表、Session 或模型。

B 在基线未合入时先做需求评审、状态矩阵、测试场景和不注册到正式应用的纯逻辑草案；不另建申请主表、数据库连接或第二套类型。基线合入后，双方记录同一实际 SHA，再接入正式代码。当前提交的 SHA 不写入自身文件；合入事实由工具结果或下一批记录追溯。

### 3.3 目录与所有权

下列新增文件是实施目标，不表示仓库已经存在。若执行时已有同等实现，复用并在 baseline 中记录映射，禁止重命名全项目来迁就本文。

```text
services/m2/main.py                    A：复用现有 M2 入口、注册业务路由
services/m2/AGENTS.md                  A 主维护、B 评审：只补 M2 局部规则
services/m2/contracts.py               A：共同 DTO、Protocol、枚举
services/m2/db.py、uow.py、state.py      A：M2 数据与事务、合法状态迁移
services/m2/application_models.py       A：申请、幂等、资源命令模型
services/m2/application_service.py      A：申请用例
services/m2/application_api.py          A：申请路由
services/m2/resource_client.py          A：M1 HTTP 适配
services/m2/resource_commands.py        A：命令版本分配、持久化、claim 与重试数据
services/m2/adapters/                   A：D 身份/主数据适配与明确测试替身
services/m2/approval_models.py          B：审批任务与记录，使用共同 Base
services/m2/approval_service.py         B：审批用例与资源结果编排
services/m2/approval_api.py             B：审批路由
services/m2/expiry_job.py、worker.py     B：超时、资源恢复、事件投递编排
services/m2/composition.py              A 主维护、B 评审：正式装配
services/m2/migrations/                 M2 单一迁移链，parent revision 先协调
services/m2/tests/                      各自行为测试；双方组合与外部契约测试
services/m2/docs/baseline.md             A：已确认基础、版本、命令与待决项
services/m2/docs/contracts.md            A 主维护、B 评审：M2 内部调用及状态规则
services/m2/docs/external-contracts.md   A：外部契约版本、能力、联调证据
services/m2/docs/decisions/、tasks/       按任务分别建文件，不争写同一篇
services/m2/docs/progress/A.md、B.md      各人自己的续做记录
services/m2/docs/automation/ROLE_A.md、ROLE_B.md  各自完整任务书
services/m2/STATUS.md                    双方随相关后端变更维护，整合时共同核对
contracts/m2.openapi.json               A 主维护、B 评审：M2 对前端公开 HTTP 契约
apps/web/src/modules/m2/AGENTS.md        A 主维护、B 评审：前端局部规则
apps/web/src/modules/m2/contracts.ts    A：与公开契约保持一致
apps/web/src/modules/m2/api.ts          A：业务请求封装，依赖公共 HTTP 层
apps/web/src/modules/m2/routes.ts       A：复用现有模块路由出口
apps/web/src/modules/m2/pages/          A：申请、我的申请、基础详情；B：审批工作台
apps/web/src/modules/m2/components/     B：审批进度/动作组件；A：申请组件
apps/web/src/modules/m2/tests/、docs/    本模块前端测试与说明
apps/web/src/modules/m2/STATUS.md        双方随相关前端变更维护
```

共同文件只能按约定小范围变更；另一人需要修改时先列方案，由主维护者整合或明确移交。两人都须更新受影响 STATUS 的本轮栏目，不以个人 progress 替代模块交接，不整份覆盖对方记录。

根依赖/锁文件、`scripts/check.sh`、`scripts/check-contracts.mjs`、`.github/workflows/`、Compose、Docker/Nginx、公共 HTTP/auth、根路由、全局样式及根规则均属共享范围。需要变更时，先在 M2 任务记录中准备具体必要改动、验收、集成人及受影响评审方；已有明确共享任务授权则按其文件范围准备改动，没有则先交付可审查方案或补丁，确认该具体共享任务后再实施。M2 总任务书不构成修改任意共享文件的授权。合入前仍须受影响维护者评审；不能借 M2 任务代写 M1/M3/D。已有 Vite 告警、部署测试兼容性、README 状态等公共维护项另行登记，不混进 M2 功能批次。

M2 schema、账号、迁移入口须先与公共维护者确定。迁移从空 PostgreSQL 可重放，种子数据单独且幂等；不使用启动时 `create_all` 代替迁移。B 新迁移先确定 parent，禁止独立产生两个 head 后视作成功，文件名前缀不能解决迁移图分叉。

### 3.4 每轮写入前的保护条件

这些条件也适用于首次保存任务书、生成文件、运行会写文件的工具，以及定时续做，不能等到提交时才检查。

1. 核对仓库实际根路径及符号链接解析结果、角色、当前分支与 origin。A 只在 `feat/m2-applications` 写入，B 只在 `feat/m2-approvals` 写入；角色目录里包含其他模块的已检出代码，不代表获得修改权。首次找到的通用克隆、队友目录和审查副本只读；不在其中切换分支、安装依赖、保存任务书或格式化，按第11节建立专用克隆。已确认属于本角色的干净专用克隆才可检出个人分支。
2. 开工记录 HEAD、已暂存/未暂存/未跟踪文件及本批允许修改的具体路径。存在来源不明的改动、非本批暂存、未完成 Git 操作或活跃写入者时，停止在该 checkout 写入并说明；不靠清空或取消暂存消除问题。可继续只读调查和独立方案准备。已知本角色未提交批次可在原分支续做，但不夹入其他批次。
3. 默认可改范围仅为第3.3节分配给本角色的 M2 文件；A 的 `contracts/m2.openapi.json` 属于明确的契约任务。其他模块的前后端、测试、契约和交接记录只读；M2共同文件也遵守主维护人分工。每批在已有授权内列精确文件清单，新增文件列目录和用途，不用仓库根目录或整个 `apps/web/` 作通配授权。
4. 编辑、生成、格式化和验证后都检查完整 tracked/untracked 差异与清单，包含重命名和删除。禁止全仓格式化、无关依赖升级、删除已有锁文件后重建，以及为消除测试失败直接修复其他模块。获授权的依赖变更通过对应工具正常生成锁文件，检查无关升级、删依赖和大范围改写。发现范围外改动则停止上传、保留现场并定位原因，不用自动 restore/reset 掩盖。
5. 不执行 `git clean`、`git reset`、`git stash`、`git rebase`、`git cherry-pick`、丢弃文件的 checkout/restore、强制切换、删除分支或改写提交历史；不自动解决冲突或采用 ours/theirs 覆盖一方。除第3.1节严格限定的个人分支快进外，不自动合并分支。不得更改 Git 全局配置、仓库远程目标、仓库访问权限或关闭检查来继续任务。
6. 每个角色工作区同一时刻只有一个写入任务。手动开发、定时触发和子任务共用同一并发检查；在首次写入前以操作系统互斥或原子创建方式取得本 checkout 的运行锁，在不入库的本地元数据中记录角色、运行标识及进程，完成后仅释放自己的锁。发现已有运行或无法判明的锁时，本轮退出并保留进度，不删除未知锁、不另开一份同时改代码；需要并行审查的子任务默认只读。后续固定使用已核实的实际工作区；路径缺失、分支被切换或远程改变时停止写入，不自动搜到另一个仓库继续。

个人机器路径、运行参数和自动化ID写本角色 progress 或不入库的本地运行记录，保存的自动化提示词使用真实绝对路径。共同 `baseline.md` 由 A 维护工程版本、接口和团队决定；B 不为记录自己的机器配置修改 A 的共同基线。共享文件和其他人已存在的记录只做获授权的局部变更，不整篇重写。

### 3.5 由 Codex 处理日常衔接

用户不必先解释“共同基础”、整理接口表或手工复制对方代码。A 的 Codex 按 A0 负责基础，B 的 Codex 按 B0 核对并准备审批工作；双方依据仓库中真实可见的文件与提交协作。

- 依赖对方进度时，通过已核实的 GitHub 仓库只读查看对方个人分支、已确认集成分支和相关 PR，读取已上传的 baseline、接口、STATUS 与对应角色 progress，记录实际来源分支及 SHA。只读查询不能移动工作分支，也不构成修改对方代码的授权；网络或权限不足则如实注明。
- 未上传的本地文件不可能由另一台电脑直接读取。A 的基础达到待验收状态后，先由本人验收上传；B 能读取该分支用于接口核对和评审准备，但只有按现有规则取得已评审集成代码并实际验证后，才称已接入。不得用自动合并、复制另一套共同文件或改写分支来跳过评审。
- 基础尚未就绪时，B 继续任务书允许的准备；缺接口时先核对实现及契约，将准确缺口和建议记录在本角色任务文件。后续随已验收批次上传后，对方可在需要该依赖时读取。只读轮询发现状态不变时保持安静，不每次要求用户催队友，不为传递进度制造空提交。
- 技术排查、接口对照、差异检查和集成方案由 Codex 完成。需要登录、本人验收、队友 PR 评审/人工合入，或真正缺少团队决定时，给用户一个具体可操作的问题或链接，并说明当前可继续的工作；已有明确答案不重复询问。评审可由 Codex提供分析，但不能代替真人表示同意。
- 这套流程不授权自动发送消息、发布评论、代他人批准、合并 PR 或直接写入公共分支。它减少手工传话，不把两个独立聊天当作共享内存，也不承诺无人验收即可完成全组集成。

## 4. 两人共用的数据与接口

本节是待 A0 评审并落实为代码的 M2 设计。已批准契约优先；变更必须同步共同版本。内部协议存放在 `services/m2/contracts.py`，公开 HTTP 定义存放在 `contracts/m2.openapi.json`；两人引用同一份类型，不复制一份自用版本。

### 4.1 标识、时间、权限和状态

- M2 申请、任务、操作 ID 为 UUID 字符串；外部 user_id、room_id、department_id 为不透明字符串，保留 D 的原义。
- API 时间收发使用 UTC `Z` 后缀，内部使用带时区 datetime，页面展示 Asia/Shanghai；区间 `[start_at, end_at)`。浏览器本地时间须明确转换，拒绝无时区输入；测试动态生成时刻。
- Actor 包含 user_id、permission_codes、department_id、managed_department_ids、managed_room_ids、manage_all_departments/manage_all_rooms（默认 false）。字段来自已验证身份适配器，不接受浏览器自报角色或管理范围。权限码和声明字段最终映射 D 契约。
- 建议权限码为 m2.apply、m2.approve.level1、m2.approve.level2；空管理集合表示无管理范围。不得为方便给管理员无限绕过。
- ManagedScope 为 `{kind: DEPARTMENT | ROOM, scope_id: str}`。申请保存经验证的院系与路由快照；缺院系/路由配置返回明确错误，不创建无人能审批的正式申请。
- 后端对所有读写校验身份和资源范围。申请人只看自己的申请；审批人按有效/历史任务及已确认范围读取必要数据。先授权过滤再分页，不能泄露全库总数。默认禁止自批。
- 申请状态：PENDING_LEVEL_1、PENDING_LEVEL_2、RESOURCE_PENDING、APPROVED、REJECTED、WITHDRAWN、EXPIRED。
- 任务状态：PENDING、PASSED、REJECTED、CLOSED。RESOURCE_PENDING 的二级任务保留但不可重复操作；终态无可操作待办。
- `version` 是申请乐观锁，每次状态变化增加；M1 `revision` 是独立的来源命令版本，两者不混用。

### 4.2 共同 DTO 与公开 API

```text
ApplicationCreate:
  room_id: str
  start_at/end_at: UTC datetime
  purpose: 去空白后 1—500 字符
  attendee_count: 正整数，不超过经验证房间容量

ApplicationView:
  application_id/applicant_id/applicant_department_id/room_id: str
  start_at/end_at/deadline_at/created_at/updated_at: UTC datetime
  purpose: str; attendee_count: int; status: ApplicationStatus; version: int
  current_step: 1 | 2 | null
  termination_reason/last_resource_error: str | null（安全说明）
  resource_phase: NONE | ACTIVATING | RELEASING | NEEDS_ATTENTION

TaskView:
  task_id/application_id: str; application_version: int
  step: 1 | 2; status: TaskStatus
  required_permission: str; managed_scope: ManagedScope; created_at: UTC datetime

ApprovalRecordView:
  record_id/application_id/actor_id: str; step: 1 | 2
  action: PASSED | REJECTED; comment: str | null; acted_at: UTC datetime

ApprovalProgress:
  application_id: str; current_step: 1 | 2 | null
  tasks: list[TaskView]; records: list[ApprovalRecordView]

OperationPendingResponse:
  operation_id: str; application: ApplicationView | null
  retry_after_seconds: 正整数
```

申请人 ID 从可信登录态取得，不接收浏览器指定 applicant_id/院系。终态 current_step=null。资源处理时 current_step=2；resource_phase 表达占用、清理或需人工处理，不增添另一套业务状态。

下面路径为 M2 公开接口提案。确认后服务端实际注册完整 `/api/m2` 前缀；公共开发/部署代理须保留相同路径转发，若团队选择剥离前缀，须统一修改契约及配置并验证，不能两边各猜一种。

| 接口 | 输入/响应 | 责任 |
|---|---|---|
| POST /api/m2/applications | ApplicationCreate → 201 ApplicationView 或 202 OperationPendingResponse | A |
| GET /api/m2/applications?scope=mine&page=1&page_size=20 | 分页申请列表，可加已定义状态筛选 | A |
| GET /api/m2/applications/{id} | 授权后的 ApplicationView | A |
| POST /api/m2/applications/{id}/withdraw | expected_version、reason 可空（最多500字）→ 200 或202 | A |
| GET /api/m2/applications/{id}/approval-progress | ApprovalProgress，遵循详情权限 | B |
| GET /api/m2/approval-tasks?status=pending&page=1&page_size=20 | 分页任务；资源处理中不得作为可操作任务返回 | B |
| GET /api/m2/approval-records?scope=mine&page=1&page_size=20 | 分页审批记录 | B |
| POST /api/m2/approval-tasks/{id}/approve | expected_version、comment 可空 → 200 或202 | B |
| POST /api/m2/approval-tasks/{id}/reject | expected_version、comment 必填1—500字 → 200 或202 | B |

对象直接返回类型化 JSON；分页为 `{items,total,page,page_size}`，page≥1，page_size 为1—100。M2 暂定错误为 `{error:{code,message,request_id,details}}`，统一处理包括 FastAPI 422；全组已有统一格式则 A0 共同替换。401 未登录、403 无权、404 不存在/按策略隐藏、409 状态/幂等/资源冲突、422 非法输入、503 已知依赖不可用。M1 的 Problem 错误由适配器映射，不混用两种格式。

所有公开写操作要求 `Idempotency-Key`，作用域为用户+动作+目标+键，保存规范化输入摘要。先重新验证身份与访问权，再查同一次幂等请求：已结束回放原结果，处理中返回同一 operation_id 的202，同键不同内容409；新操作才检查 expected_version 和状态。数据库唯一约束防并发重复；幂等记录和业务意图同事务持久化，不用短 TTL 静默删除导致重复执行。

202 时页面轮询已有申请详情；申请尚未持久化则按返回间隔重放原键/原输入。不得自动生成新键再次批准。占用冲突需清理时先202；清理完成回二级待审后，该次批准操作结束为 RESOURCE_CONFLICT，重复原键回放此结果。用户刷新 version 后可用新键发起新的逻辑审批。

### 4.3 A/B 的内部调用与事务

以下为同步接口方案；A0 若选择异步，应整体调整并锁定共同签名。

```python
class M2UnitOfWork(Protocol):
    session: Session
    def __enter__(self) -> "M2UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

class ApprovalPort(Protocol):
    def initialize(self, *, uow: M2UnitOfWork, application: ApplicationView) -> None: ...
    def close_pending(self, *, uow: M2UnitOfWork, application_id: str,
                      reason: str, now: datetime) -> None: ...
    def progress(self, *, uow: M2UnitOfWork, application_id: str,
                 actor: Actor) -> ApprovalProgress: ...

class ApplicationPort(Protocol):
    def get(self, *, uow: M2UnitOfWork, application_id: str) -> ApplicationView: ...
    def transition(self, *, uow: M2UnitOfWork, application_id: str,
                   expected_version: int, expected_status: ApplicationStatus,
                   target_status: ApplicationStatus, current_step: int | None,
                   reason: str | None, now: datetime) -> ApplicationView: ...

class RoomBlockPort(Protocol):
    def put_state(self, *, command: RoomBlockCommand) -> RoomBlockResult: ...

class ResourceCommandStore(Protocol):
    def new_target(self, *, uow: M2UnitOfWork, application: ApplicationView,
                   desired_status: BlockStatus, operation_id: str,
                   resume_target: ResumeTarget | None) -> RoomBlockCommand: ...
    def latest(self, *, uow: M2UnitOfWork,
               application_id: str) -> RoomBlockCommand | None: ...
```

BlockStatus 为 ACTIVE/RELEASED，ResumeTarget 为 PENDING_LEVEL_2/EXPIRED。新目标在已锁定或条件更新的申请上分配持久化 revision；同一 operation_id+目标重复调用返回既有命令，不增加版本。重试原命令不得调用 new_target。A0 还须把 claim/续租/结果保存/重试安排的准确接口写入共同代码，B 只依赖这些接口，不自己实现第二套命令仓储。

resume_target 属于持久化的本地恢复元数据，不属于不可变HTTP请求内容；只允许从 PENDING_LEVEL_2 提升为 EXPIRED，迟到冲突回执不得降回待审。超时清理复用原最终审批 operation_id，先查现有 RELEASED；如已存在则复用。目标更新与当前命令、申请状态/version检查在同一事务内完成，不因更新目标改请求载荷或增加revision。

- A 提供工厂、Base、ApplicationPort、命令仓储和唯一合法状态表；B 实现 ApprovalPort、审批编排与 worker。A/B 在同一 M2 服务内调用，不拆成两个独立后端或数据库。
- 每个用例创建独立 UoW。同一短事务中的申请、任务、审批记录、幂等记录、资源意图共用 Session。顶层用例 commit；port 不独立 commit/rollback，可 flush；异常或未提交退出回滚并关闭 Session。
- 申请创建与 B.initialize 同事务；撤回、过期、驳回与关闭待办同事务。测试故意让初始化/关闭抛错，确保没有部分提交。
- 二级批准先在短事务检查资格、version、状态和新鲜服务端时间，进入 RESOURCE_PENDING 并落盘 ACTIVE 命令；结束事务后才请求 M1，再以新事务核对结果。不得持数据库锁等待网络。
- 同事务持久化 ApprovalAttempt 或等价的审批意图：operation_id、申请ID、task_id、原审批人actor_id、原comment、规范化请求摘要、请求时间、原expected_version、关联ACTIVE命令ID与公开幂等记录。每次逻辑批准唯一，重放复用。B的审批模型负责这些事实，A的共同类型和幂等/命令仓储提供关联；不能只存在HTTP请求内存中。回执或worker恢复时，在同一短事务完成申请、任务、唯一审批记录与原operation的幂等终结结果；审批人仍记原人，恢复执行者另作系统审计，不把worker冒充审批人。资源冲突清理或过期终结也更新原operation，避免客户端永远收到202。
- 审批状态修改统一经过 ApplicationPort；不得暴露任意改状态 HTTP 接口。内部签名不代替顶层身份/时限校验。
- 协议仅依赖共同类型；`composition.py` 注入实际实现，避免循环 import。生产/正式集成配置不得自动回退测试替身。

### 4.4 与仓库 M1 契约对齐

依据 `contracts/m1-room-blocks.openapi.json@0.1.0-proposed`，实际实现及评审仍需确认。

```http
PUT /internal/v1/room-blocks/m2/{sourceId}
Authorization: Bearer <M2服务凭证>
X-Correlation-Id: <同一命令重试沿用的关联ID>
Content-Type: application/json

{
  "roomId": "room-101",
  "revision": 1,
  "status": "ACTIVE",
  "startsAt": "2026-10-23T08:00:00Z",
  "endsAt": "2026-10-23T10:00:00Z"
}
```

示例时间仅解释格式，测试应使用动态未来时间。sourceId 始终为同一个 application_id，不因重试/再次审批改变。请求只能有上面五个字段；不能塞入内部 command_id、operation_id、reservation_id 等额外字段。revision 为1至9007199254740991，来源全生命周期递增。外部幂等来自 sourceId+revision+完整请求，不能依赖 M1 支持浏览器使用的 Idempotency-Key 语义。

RoomBlockCommand 保存 command_id、application_id、revision、desired_status、room_id、starts_at、ends_at、correlation_id、请求摘要及创建时间；发送内容一旦落盘不再修改。运行元数据另存尝试次数、next_retry_at、租约、命令状态和最后错误。重试用相同版本、内容和 correlation_id。

M1 当前没有查询/lookup 接口。未知结果通过相同 PUT 重放确认；终结在途占用通过更高版本 RELEASED，不臆造 GET。服务令牌签发与校验须由 D/M1 确认，不用用户令牌冒充服务身份，不开放匿名写回。

| RoomBlockResult 分类 | 判断与处理 |
|---|---|
| APPLIED | HTTP200 且 sourceSystem=M2、来源、房间、revision、目标状态、时段和 appliedAt 验证成功 |
| OCCUPANCY_CONFLICT | 409 且 code=ROOM_OCCUPANCY_CONFLICT；进入有序清理 |
| STALE_REVISION | 409 且 code=STALE_REVISION；已知被本地更高命令取代的旧回执可忽略，其余为一致性故障 |
| PAYLOAD_MISMATCH | 409 且 code=REVISION_PAYLOAD_MISMATCH；停止该命令自动重试并报告，不换版本掩盖错误 |
| UNAVAILABLE_OR_UNKNOWN | 超时、断连、503、无效成功响应及可能已生效的异常；保留意图与退避重试 |
| NONRETRYABLE | 400/401/403/404/422 等确定错误；记录原因并等待配置/契约修复，不盲目重试 |

M1 错误体为 `application/problem+json`，包含 type/title/status/code，可能含 detail/instance/correlationId。未知409不能按房间占用冲突处理。通用成功 schema 的 endsAt 可选，M2 的有限时段确认需要双方在契约评审明确必须返回并匹配 endsAt；在提供方保证前，这项收紧校验只算待确认要求。

### 4.5 状态迁移与迟到请求的处理

本节采用第2节建议政策，先由 M1/M2 共同确认。申请处于两种 PENDING 状态必须满足：从未发过 ACTIVE，或此前占用尝试已经由更高版本 RELEASED 确认清理。只有这个不变量成立，才能直接撤回/驳回/过期而无需网络释放。

| 当前情况 | 同事务动作/下一步 |
|---|---|
| 一级待审，合法通过且未截止 | 二级待审；完成一级任务和记录，创建唯一二级任务 |
| 两种待审，合法驳回/本人撤回 | REJECTED/WITHDRAWN，关闭待办并记录原因 |
| 两种待审，now≥deadline_at | EXPIRED，关闭待办并记录系统事件 |
| 二级待审，最终通过请求未截止 | RESOURCE_PENDING，落盘 ACTIVE(r)，二级任务不可重复操作 |
| 当前 ACTIVE(r) 获匹配成功，确认事务时未截止，未被新命令替代 | APPROVED，二级任务 PASSED，唯一最终通过记录 |
| ACTIVE(r) 明确房间占用冲突 | 仍 RESOURCE_PENDING，落盘更高版本 RELEASED，恢复目标为二级待审；不写最终通过 |
| RESOURCE_PENDING 到截止，无论占用结果是否已知 | 持久化更高版本 RELEASED，恢复目标为 EXPIRED；停止安排旧 ACTIVE 重试 |
| 已有 RELEASED 在途时到截止 | 保留同一释放命令，更新本地终结目标；不为每次扫描增加版本 |
| 当前 RELEASED 得到匹配成功且已截止 | EXPIRED，关闭待办；该次批准操作终结为过期失败 |
| 当前 RELEASED 得到匹配成功，未截止且目标是二级待审 | 回二级待审，version 增长、保留待办；本次批准终结为资源冲突 |
| RELEASED 未确认或需人工处理 | 保持 RESOURCE_PENDING，显示 RELEASING/NEEDS_ATTENTION；不得声称已无残留 |
| 旧 ACTIVE/旧回执迟到 | 不覆盖较新清理意图或终态；确保最新 RELEASED 最终确认 |
| APPROVED 到审批截止 | 不再按审批超时撤销；M1 根据有限占用区间计算可约性 |

这里选择“冲突后先确认 RELEASED，再允许下一次审批”，目的是封住旧 ACTIVE，避免依赖冲突是否消耗版本的未决细节；代价是 M1 不可用时不能立即再次审批，要在评审中说明。下一次真正的审批才新建更高 ACTIVE revision，仍使用同一 sourceId。

M1 必须以来源版本墓碑拒绝迟到旧 ACTIVE：释放先到也保存版本，释放后到则移除本来源，不能解除 M3 或别的申请来源。真实联调必须验证两种到达顺序。M2 不直接修改 M1 的任何表或整间房间的全局可用开关。

每次最终确认在新短事务获取可信当前时间，`now>=deadline_at` 算截止；不能复用网络调用前的 now。回执写回须同时核对申请状态、当前命令和更高版本意图；发送方在发送前检查命令仍有效。数据库 claim/租约减少重复发送，但网络在途竞争仍靠 M1 版本协议保护。

503/未知结果采用有界退避、持久化下次时间及告警；重试耗尽保留命令和恢复入口，不能丢弃或标成功。对确定不可重试错误保留 RESOURCE_PENDING 并标需要处理，不能把曾经未知的占用推断为不存在。A 只负责命令与网络适配，B 负责状态编排、超时和唯一受管理 worker；两边不能各起一套无限重试循环。

### 4.6 前端组合与公共入口

A 提供申请表单、我的申请及基础详情；B 提供审批工作台、ApprovalProgressPanel、ApprovalActionPanel。进度组件接收 application_id；动作组件接收 application_id/task_id/application_version，完成操作 emit `changed`，父组件刷新。双方使用共同类型和 `m2/api.ts`，不复制登录态或请求客户端。新页面注册到现有 m2/routes.ts，通常不动根路由。

公共 HTTP、auth、开发代理和 Nginx API 转发当前尚未实现；已有共享登录入口页面不等于真实登录和鉴权能力。需先由明确的公共任务约定入口与鉴权；M2 页面不得硬编码 localhost:3102、公网IP或服务凭据。测试环境 API 当前仅绑定服务器本机地址，静态 SPA 不能自动转发 API。M2→M1 的调用只在后端发生，前端不能依次调两个服务代替一致性编排。

页面验证正常、加载、空数据、失败、无权限、处理中、过期及版本冲突状态。前端按钮仅作提示，权限始终由后端执行。局部样式 scoped，避免影响其他模块。

## 5. 外部依赖与工作量边界

A 维护 `services/m2/docs/external-contracts.md`，记录提供方/负责人、版本与SHA、请求与错误、身份、URL配置、重试、实现/测试/部署状态、缺口及下一步。B 使用同一份记录。

| 依赖 | M2 需要的能力 | 未就绪时如何推进 |
|---|---|---|
| D 身份/RBAC | 可信用户、权限和管理范围；服务间身份 | 写清适配端口与隔离测试身份；正式请求禁止信任自报角色 |
| D 房间主数据 | 稳定ID、容量、院系、开放范围 | 用明确 fixture 测校验，真实数据接入保持 BLOCKED |
| M1 | 幂等版本写回、冲突政策、释放墓碑、来源追溯 | 实现协议适配及外部替身；不得把模拟成功当真实座位限制 |
| 通知/审计 | 事件契约、去重、重试、查询权限 | 在 M2 本地事务记录 outbox/审计事实，外部投递待契约就绪 |
| M3 | 维修限制由 M1 汇总，释放 M2 不解除维修 | 与 M1/M3 联调验证；M2 无须直接导入 M3 |
| 公共 Web/部署 | HTTP入口、鉴权、代理、迁移、worker配置 | 限定公共子任务和评审责任，复用现有流水线 |

通知失败不逆转已完成业务，但未投递须留重试/失败证据。本地审计记录不等于公共审计已接通。其他业务模块缺接口时在 M2 记录缺口，不代改其代码、测试、规则或 STATUS。

### 5.1 临时依赖的登记、替换与清理

执行时以实际根 `AGENTS.md` 为准。尚未实现的外部能力只能在本角色获授权的 M2 消费端范围内建立最小适配器或替身，不复制提供方业务实现，不修改提供方表结构。先记录所依据契约的路径、版本和批准状态，以及临时假设、尚未解决的差异；提案与替身行为都不能替代团队政策决定。

- 每项依赖使用稳定 ID，例如 `M2-TEMP-D-IDENTITY`，在对应文件或目录 README 写明 `TEMPORARY-DEPENDENCY` 与该 ID。测试替身应提供消费者所需的成功和失败行为，但不得替换正在验证的 M2 业务逻辑。对方 M2 实现未就绪时可按第3.2节和角色清单独立验证本方；只有使用双方真实实现时才能声称 A/B 组合通过。必须通过明确的开发/测试配置启用，运行模式可见，正式运行使用真实提供方；禁止真实服务失败后静默退回模拟成功。
- 在本批模块任务记录中维护精确清理清单，并从相关 `STATUS.md` 链接到它。逐项记录消费者/提供者、缺失能力、契约状态、临时假设、精确文件路径、配置与启用方式、责任组、清理触发条件、真实集成验收、清理后应保留的代码。个人 progress 可链接该记录，不能替代模块交接清单。
- 交接分别说明“消费者已实现”“替身验证通过”“真实提供方尚未验证”，不能合称已完成集成。
- 真实提供方就绪后，先建立获授权的集成任务，核对最终契约、接入真实适配器并完成真实集成检查。只有通过后，才在本次明确授权范围内移除清单列出的临时实现、专用 fixture 和启用配置，再运行相关检查及 `bash scripts/check.sh`，更新任务与 STATUS。保留正式业务逻辑、真实 API 客户端、错误处理和长期测试；仅属于临时替身的部分才纳入清理。
- 标记本身不是删除授权。涉及其他组文件、共同文件或超出当前任务范围时，先按原有范围与评审规则落实具体集成任务；不得为清理而覆盖他人代码、自动解决冲突或丢弃改动。

## 6. 定时开发的执行规则与交接

默认计划采用 Asia/Shanghai：每天（含周末）10:00、14:00、17:00 触发开发，每轮只推进一个实际小任务；Git提交、推送及已授权PR创建/更新在09:00—18:00内发起，具体边界为 `09:00 <= 当前本地时间 < 18:00`。执行到上传步骤时重新读取当前时间，不能只看本轮启动时间。18:00后可完成必要验证与保存进度，上传留到下一次窗口内运行。保留真实执行时间，不倒填时间、不制造空提交，也不为形成时间分布故意切碎任务。

用户在窗口内验收授权后可立即上传；窗口外收到授权则记录 WAITING_UPLOAD_WINDOW，保留已验收批次和原授权，在下一次窗口内运行优先核对并完成上传，默认是次日10:00的计划触发。等待期间不向已验收批次添加新内容，不要求用户对未变化的同一批次重新批准；保存状态后结束本轮，不用长时间sleep或轮询等到窗口。状态仅写聊天或忽略的本地运行元数据，避免为排队改动已验收文件。没有实际改动或没有人工验收授权，就不提交。没有运行中的应用/可用机器时，排队本身不保证按时执行，恢复后仍先检查当前窗口。

每次先读适用规则、本人任务书、共同 baseline/契约、本人 progress、本模块 STATUS 和实际工作树，并通过第3.4节保护检查。文件未建立不当成已完成；规则与文件矛盾时核实代码和证据。不得重复初始化已做的工作。

每轮只推进一个依赖满足、可审查的小批次：按现有AI任务模板写方案/需求/范围/验收 → 实现 → 必要验证 → 同步交接 → 提供差异。已知本任务未完成改动可继续；来源不明的修改须保留并核对。已有同一工作区活跃写入者时不再启动第二份。

```text
READY → IN_PROGRESS → READY_FOR_REVIEW
                   ↘ BLOCKED_DEPENDENCY
READY_FOR_REVIEW → 本人实际验收并授权 → 窗口内 COMMIT_AND_PUSH
                                      ↘ 窗口外 WAITING_UPLOAD_WINDOW
WAITING_UPLOAD_WINDOW → 窗口内核对内容及原授权 → COMMIT_AND_PUSH
COMMIT_AND_PUSH → PUSHED_WAITING_REVIEW → 人工合入 → INTEGRATION_CHECK
INTEGRATION_CHECK → PASS / FAILED（对应真实修复任务）
```

达到 READY_FOR_REVIEW 后等待验收，不积累无关批次；修复本批次后重新展示差异，变化部分重新验收。缺外部依赖时可继续无关准备和内部测试，不伪造提供方能力。上传中断只恢复尚未完成的步骤，不反复提交相同内容。

个人 progress 包含任务ID、共同SHA、契约、范围、真实验证、批次、依赖、下一步和已发生的历史PR。后端/前端 STATUS 同步记录当前已实现、已测试、已部署范围、公开入口、契约、命令、依赖、下一集成步骤。只记录已发生的评审/部署，当前未提交批次写工作区事实。不同电脑或分支通过提交与 PR 同步；不能依赖两个 Codex 自动共享聊天或未提交文件。

## 7. GitHub 提交、评审和部署证据

### 7.1 具体批次验收后上传

每批提供：批次ID、base HEAD、修改/新增/删除文件、完整差异、测试结果、模拟范围、迁移/契约影响、未完成项。新文件要展示内容，不能只看 `git diff` 漏掉 untracked。可由工具计算文件 SHA-256 清单和总摘要，存放在 Git 忽略的本地临时目录或 `.git` 对应的本地元数据路径，避免修改共享 .gitignore 或自引用；不把当前清单摘要写回它覆盖的文件。

用户明确表示已验收当前可识别批次并授权提交/推送/PR 即有效，不必手抄长 SHA；如同时存在多个批次则先明确是哪一批。机器核对授权后内容未变化。AI 自己写 approved=true、泛泛“继续开发”不等于人工验收。

授权后按第6节检查上传窗口：窗口内可立即执行下列步骤，窗口外保留授权待下一次窗口内运行。发起commit、push及PR写入前均重新检查时间；已开始的网络请求可能在窗口结束后返回，按真实结果记录，不更改时间戳。无需逐条重复确认已授权步骤：

1. 确认本人真实Git身份、准确的角色分支、HEAD与验收内容；不代改身份冒充队友。用 `git remote get-url --all origin` 与 `git remote get-url --push --all origin` 核对读取和推送地址，均须对应 `github.com/FDU-Group16/Project1`；本任务只接受单一已核实的推送目标。发现其他地址、多个推送目的地、镜像推送配置或未知仓库时停止，不自动更改配置绕过。
2. 显式 stage 已验收文件，不盲目 `git add .` 或 `git add -A`。核对整个 index 的 staged diff 与验收内容完全一致；已有非本批暂存时停止，不顺带提交，也不自行取消暂存。提交前后均核对差异，工具或钩子新增的未验收内容不得上传。
3. 上传前检查所有待推提交，不能只看最后一次提交。查询准确的远端个人分支；新建远端分支时以确认的工程基线核对本方增量，已有时核对远端尖端到本地 HEAD 的提交和祖先关系。只允许已确认团队基线历史及本人已验收且获上传授权的批次；未知提交、异常大范围改动或远端分叉时停止。普通 push 拒绝后不得强推或自动整合远端。
4. 仅使用下列与本人角色对应的显式命令，且每次执行前重查第3.4节和上传时间。禁止裸 `git push`、`--all`、`--mirror`、`--tags`、`--delete`、任何强推（含 `--force-with-lease`）、带 `+` 的 refspec、推送其他分支或标签：
   - A：`git push --no-follow-tags origin HEAD:refs/heads/feat/m2-applications`
   - B：`git push --no-follow-tags origin HEAD:refs/heads/feat/m2-approvals`
5. 授权含 PR 且目标已确认时，明确指定仓库、本人 head 和已确认 base；创建/更新前检查实际 `base...head` 的全部文件、提交及差异。基线不齐造成全组骨架入 PR、含其他人的未集成工作或无关变更时先停下，不能靠描述解释掉。写清需求、行为、测试、依赖、迁移和评审范围；创建后按当前应用要求附到聊天。不自动合并，不启用 auto-merge 或加入 merge queue，不为绕过差异而擅自修改已有 PR 的 base。
6. 回报实际 commit、远端分支、PR URL。push失败或执行中已到窗口外时，区分“本地已提交”“远端已成功”“PR尚未创建”等状态；保留待办，下一次窗口内只恢复未完成步骤，不重复commit。
7. 上传后新增状态记录不偷偷夹入已验收批次；工具结果记录当前事实，下个真实批次补历史即可。

PR 合并、处理冲突、生产发布不包含在本授权中。公共层、schema、跨模块契约由受影响方评审；本人审查自己的AI变更和队友PR Review分别留下证据。仓库管理员实际启用保护规则/required checks后才称强制门禁，不能仅凭文档作此承诺。

### 7.2 提交与部署的区别

现有普通 CI 监听 main/m1/m2/m3 的 push 和 PR；个人 `feat/*` 分支单纯 push 不触发该 push 检查，创建 PR 后才能触发 pull_request 检查。老师任务书第2—3页要求提交与合并请求自动触发构建、测试失败阻止后续阶段，因此个人开发分支的 push 检查覆盖是全组必须补齐的 E-03 工作，不能当作可选优化。由流水线维护者承接明确的共享任务，限定 `.github/workflows/ci.yml` 等必要路径并按受影响方评审；用真实个人分支 push 和 PR 分别验证检查触发，确认失败阻断。M2 先在任务/依赖中登记并协调，当前总任务书不授权任意改写公共流水线，也不把暂缺检查的个人 push 写成已通过 CI。

只有进入 develop 才触发既有测试部署。个人 push、PR检查成功、m2集成、develop合入、staging部署成功分别记录；自动部署通过仍不等于业务联调通过。生产审批、发布tag、迁移与回退演示由全组发布安排。

GitHub应展示真实链条：需求/方案/验收 → 功能和测试提交 → 队友Review → 合入 → Actions → 业务验收。提交示例：`feat(m2): 提交申请并原子创建首级待办（M2-02）`、`fix(m2): 处理实测的迟到占用回执（X-02）`。不为了次数分拆无意义改动或创造虚假故障。

## 8. 验证门禁与集成顺序

已有 `bash scripts/check.sh` 只覆盖 M1 契约基础检查、Python编译、四服务健康响应、Vue类型和构建。`scripts/check-contracts.mjs` 当前只读取 M1 的契约文件。新增 M2 接口和测试不会自动被这些检查覆盖。

A 准备限定共享改动：让新 M2 契约被校验，将 M2 行为与真实数据库测试接到统一入口或两个现有工作流共用的明确步骤，并提供测试数据库准备/迁移流程。需共同维护者评审；不另造与 develop 部署脱节的绿灯流水线。

| 门禁 | 验证内容 | 责任 |
|---|---|---|
| G0 基础 | 锁定安装、现有 check.sh、M2导入、前端构建 | A 接入，双方执行 |
| G1 契约 | 共同类型、真实JSON往返、错误/分页、协议字段、适配响应 | A 基础，B provider/审批测试 |
| G2 数据 | 实际PostgreSQL空库迁移、唯一head、幂等种子、约束与事务 | A 组织，B补迁移 |
| G3 双人组合 | 真实A提交→真实B待办→查询→两级审批；初始化/关闭失败整单回滚 | A 装配、B主场景 |
| G4 竞争与恢复 | 幂等、权限、跳级、自批、截止、重复worker、迟到回执 | 各自业务及共同场景 |
| G5 跨服务 | 真实M1 HTTP占用/释放、座位查询或预约行为、来源与时间边界 | A 对接、B编排、提供方参与 |
| G6 部署 | 全组staging页面/API/数据库/worker、版本、迁移、生产审批与回退 | 配合公共发布负责人 |

G3/G4 使用真实 M2 两人的实现和 PostgreSQL，只允许替身外部 D/M1；不能 mock 掉对方业务然后称组合成功。SQLite/内存列表不能作为PostgreSQL事务、唯一约束和并发的验证证据。

至少覆盖：

1. 提交与待办同事务；初始化失败无申请/幂等结果残留；重复提交仅一申请一待办。
2. 撤回/驳回/超时与关闭待办同事务；失败回滚；审批与这些动作竞争只有合法胜者。
3. 权限、院系/房间范围、禁止自批、跳级、过期、终态与分页越权。
4. 最终批准原键重放、不同输入冲突；申请version和M1 revision彼此独立。
5. M1已应用ACTIVE但响应丢失、M1成功但M2落库失败，原PUT重放恢复；重启后仍正确记录原审批人/意见并完成原幂等操作结果。
6. 截止时ACTIVE先到/RELEASED先到两种顺序；旧回执不能覆盖清理或终态。
7. RELEASED响应丢失，重放确认；重复扫描不无限增加revision。
8. 房间冲突先清理后再审批；同来源更高ACTIVE版本；三种409分别处理。
9. 释放M2不解除M3维修/其他申请；相邻半开时段不误伤。
10. 无人打开网页也能在已约定延迟范围内执行过期作业；多worker重复运行不产生矛盾结果。

第5—9项的真实提供方语义仍须G5实测；外部替身通过只代表内部编排验证。依赖缺失记 BLOCKED，没运行记 NOT_RUN，失败记 FAILED，不把 skip 当 PASS。

节奏：M2-BASE → 先打通真实申请+一级待办 → 一级/二级与页面 → 真实M1 → 超时/故障恢复 → 全组环境验收。每一轮在集成版本上组合测试，不等所有代码写完才第一次合在一起。故意破坏实现以确认关键测试会失败时，必须使用一次性临时副本及隔离测试资源，原开发工作区和已验收批次保持不变；不在真实分支先破坏再靠恢复交付，不提交破坏代码。

### 8.1 课程评审与团队交接

这两份文件只承担 M2 的实施与交接，课程整体交付仍需全组配合。老师任务书第4—5页的评审节点没有统一日期，由团队安排；每次提交真实证据，不提前写为已通过：

| 节点 | 全组应准备的内容 | M2 提供的材料 |
|---|---|---|
| 项目启动 | 成员、模块认领、组内分工、D 归属方案与书面决策 | A/B 责任、共同文件主维护人、公共层工作量与待确认项 |
| 第一次 Review | 需求基线、任务与依赖、架构和首轮功能、AI 协作规则、风险 | M2 需求/政策、共同接口、首个真实申请到一级待办闭环及相应提交/测试；尚未实现就明确缺口 |
| 第二次 Review | 主功能和真实集成、集成测试、流水线自动迁移、提交到部署全流程与质量保证 | 审批/超时/恢复、真实 M1 写回、A/B 组合、迁移与测试有效性证据 |
| 期末展示 | 完整功能、人机协作过程和工程实践的实际演示 | M2 场景、需求到代码/测试/PR 的追溯、真实人员的验收/评审与工程伦理决策 |

期末全组须实际演示五项：全新环境经流水线部署；一次提交自动触发构建与测试；含 schema 变更的部署及数据演化；生产审批发布与回退；模块经网络调用另一个模块并展示状态写回。截图、健康检查和静态页面不能替代这些演示。M2 提供本模块所需迁移、worker、接口及联调材料，部署维护者组织全组环境和发布，不默认把全部发布工作交给 A。部署版本还须有可回溯 Git tag、提交与迁移记录，仅有镜像 SHA 不能把课程的 tag 要求写为已完成。

老师任务书第3页另要求每人基于本人真实参与的工作撰写课程论文，说明工程伦理问题、采取的措施和仍有疑问的地方。A/B 各自保留实际需求讨论、验收、评审、故障和决策证据，不以 AI 对话或虚构参与替代 GitHub 过程；两份代码任务书不会自动代替个人论文。

## 9. 命令、配置、调度与完成标准

### 9.1 已有命令与需要落地的命令

通过第3.4节检查后，在本角色专用仓库根目录按用途执行的已有命令；先读实际脚本，核对文件、进程、网络和数据写入目标：

```bash
uv sync --frozen
npm --prefix apps/web ci
bash scripts/check.sh
uv run --frozen uvicorn services.m2.main:app --host 127.0.0.1 --port 3102
npm --prefix apps/web run dev
```

依赖安装、测试、后端服务和前端服务按用途分别执行；长驻服务需要独立终端，不把整段当一条串行任务。A0 在 `services/m2/README.md` 写出经过验证的M2命令。建议目标包括 `uv run --frozen pytest services/m2/tests`、明确配置路径的Alembic命令、`uv run --frozen python -m services.m2.worker`；这些目前尚未实现，不能预写成功。若选择其他工具，用双方统一的真实命令替换。常规安装和验证不得隐式更新依赖锁文件，所需依赖变更按第3.3节单列任务。

测试、迁移、种子、worker及真实 M1/D 调用均可能修改数据，启动前必须明确实际数据库主机/库/schema/账号、服务地址及专用测试用户、房间、申请和时段，日志不输出密码或令牌。默认使用本人隔离测试资源；不能因为 `.env` 存在就沿用共享 staging 或生产凭据，也不能因本地启动服务便认为其连接的资源是本地。未知目标或没有隔离配置时，依赖它的写入测试保持 BLOCKED；数据库测试/清理入口应拒绝未经确认的目标，不能自动退回通用 DATABASE_URL。

迁移及 fixture 只作用于明确测试数据库/schema；不清空共用数据库，不修改 M1/M3/D 的表或迁移链。G5 真实服务测试不等于获准操作全组线上数据：在隔离服务中验证，或按参与方已确认的共享联调范围执行；测试清理只处理本轮创建且可追溯的数据，不释放别人的房间占用。共享环境迁移、worker启动和发布需具体部署任务授权，不能由个人开发计划直接执行。

启动服务前检查端口和容器归属；占用时报告或使用本轮可配置的新端口，不杀进程抢端口。只停止本轮创建且归属明确的进程/容器；Docker测试使用独立项目名、网络和卷，不执行全局 prune、共享 Compose 的 down（尤其带 -v）或停止他人服务。测试 worker 使用隔离配置、记录PID与停止方式，验收结束后停止本轮测试进程，防止继续扫描共享数据。

### 9.2 配置与部署交接

以下为M2建议配置名，先沿用实际已有同义配置；根.env样例/Compose变更按共享任务评审。秘密只通过环境或密钥管理传入，不放仓库、VITE变量或日志。

| 配置 | 含义 |
|---|---|
| M2_DATABASE_URL | M2专用schema/账号连接，具体隔离方案先确认 |
| M2_EXTERNAL_MODE | 显式test/stub/real模式，正式环境real，缺配置不降级 |
| M2_APPROVAL_TTL_HOURS | 建议24，待政策确认 |
| M2_APPROVAL_BEFORE_START_MINUTES | 建议30，待政策确认 |
| M2_EXPIRY_SCAN_SECONDS | 建议60，允许处理延迟和负载需验收 |
| M2_RESOURCE_TIMEOUT_SECONDS | M1请求超时，结合重试和截止政策配置 |
| M1_BASE_URL | M1服务根地址，Compose内使用服务网络地址 |
| M2资源重试/租约配置 | 最大次数、退避、claim超时，具体名字A0统一 |
| D身份/主数据/通知审计配置 | 按真实公共契约，包含服务凭证来源但不记录值 |
| 浏览器API入口 | 公共HTTP层统一，不能把M1内部地址暴露给组件 |
| 部署SHA | 复用现有部署版本追溯方式，新增运行时字段须明确落地 |

B 的业务超时worker持续由应用部署环境管理，与Codex周期开发完全不同；不依赖个人电脑或Codex在线才过期。当前Compose只有四API、Web和PostgreSQL，worker、数据库迁移、业务就绪检查都要按明确任务接入。避免在每个Uvicorn进程无控制地启动一份扫描器。

交接涵盖容器入口、网络、迁移执行顺序、API/worker使用同一M2存储、claim策略、日志、告警、业务就绪与回退兼容。`/healthz` 只说明HTTP进程能响应，不证明数据库或M1/D可用。迁移失败不得开始依赖新schema的版本；不可逆迁移不能简单靠回退旧镜像声称恢复。

### 9.3 每轮结果与完成定义

每轮输出：任务/需求、范围与方案、实际修改、命令及结果、模拟/真实边界、待审批次、依赖和下一步。有新成果、首次阻塞、失败变化、完成或需人工行动时通知；状态没变化保持安静，不刷空提交，不未经授权给队友或其他聊天发消息。

分别判断“本人功能完成”“A/B组合通过”“M1/D真实接入通过”“全组部署验收通过”。每个结论绑定代码SHA、契约版本、环境和场景；文档不能保证未来接口任意变化后仍可直接集成。公共定义或提供方实现变更后重跑相关验证。


## 10. 角色 B 的任务清单

你负责审批、截止撤销、资源恢复编排及业务worker。A负责申请、M1客户端、命令仓储和M2内部共同基础。不得另建正式应用、申请主表、ORM Base/Session、登录或M1客户端。

### B0：需求与共同基线评审

- [ ] 核对项目、分支、当前develop与A的M2-BASE，确认基础实际合入SHA。
- [ ] 基线未到位时先准备审批权限、状态矩阵、截止/竞争场景及独立纯逻辑草案，不阻塞所有准备。
- [ ] 参与第2节业务规则决定，核对禁止自批、管理范围、时限和冲突清理方案。
- [ ] 核对ApprovalPort/ApplicationPort/RoomBlockPort/ResourceCommandStore准确签名及事务责任。
- [ ] 不匹配时给A具体提案，由共同基线统一；不在自己分支另复制一套协议。
- [ ] 基础合入后安全取得同一代码，验证真实共享类型与UoW，再接数据库和路由。

完成标准：运行的是同一M2模型和事务入口，明确共享SHA和未决依赖；仅有自建替身不算共同基础完成。

### B1：审批任务、记录和提供者接口

- [ ] 使用共同Base建立任务/审批记录模型，与A协调迁移parent和唯一约束。
- [ ] 实现ApprovalPort.initialize、close_pending、progress；仅使用传入UoW，不独立commit。
- [ ] 初始化只建唯一一级任务；重复调用安全；历史记录与任务不覆盖删除。
- [ ] 查询按申请/审批范围授权，记录实际处理人、动作、意见和时间。
- [ ] Provider测试使用共同协议；与真实A提交用例装配，验证正常、重复、初始化/关闭故障回滚。
- [ ] 优先打通提交→首级待办可查询，而非先做完整审批界面再集成。

完成标准：A不用改签名即可调用真实B；申请与任务同事务的真实PostgreSQL测试通过。

### B2：审批接口、进度组件与工作台

- [ ] 实现待办/已处理列表、分页、进度、审批动作和后端权限过滤。
- [ ] 通过/驳回校验身份、管理范围、禁止自批、步骤、状态、version和当前截止。
- [ ] 一级通过与一级记录、二级任务同事务；驳回与关闭任务同事务；统一调用ApplicationPort。
- [ ] 公开写操作遵守共同Idempotency-Key规则，已成功原请求重放不会被旧version误判。
- [ ] 提供ApprovalProgressPanel/ApprovalActionPanel，准确Props与changed事件；共用m2/api.ts。
- [ ] 资源处理中禁重复操作；终态无可操作待办；前端隐藏按钮不能替代后端鉴权。
- [ ] 检查加载/空/错误/权限/版本冲突/窄屏/键盘，并更新对应STATUS。

完成标准：一级通过不提前批准，不能跳级、自批、越权或重复审批；组件可直接组合到A详情页。

### B3：最终审批和资源结果编排

- [ ] 短事务进入RESOURCE_PENDING并调用A命令仓储落盘ACTIVE，提交后调用RoomBlockPort；不持锁等HTTP。
- [ ] 同事务持久化原审批人、意见、任务ID和operation/幂等/命令关联，崩溃恢复使用原审批意图；worker不冒充审批人。
- [ ] 匹配成功且确认事务时未截止、当前命令未替代，才APPROVED并写唯一最终PASSED记录。
- [ ] 占用冲突进入释放清理，保持RESOURCE_PENDING；更高RELEASED确认后才回二级待审。
- [ ] 未知结果202并持久化恢复，不生成新逻辑审批或假装无占用。
- [ ] 已过截止改清理目标EXPIRED；已有释放在途时复用，不能每次扫描升revision。
- [ ] 核对迟到回执/更高版本，不让旧ACTIVE成功覆盖释放意图、过期或其他终态。
- [ ] 区分三种409；不可重试错误保留处理状态与安全原因，不靠升版本掩盖错误。
- [ ] 与A联测M1成功但本地落库失败、响应丢失、截止竞争等恢复。

完成标准：只有可靠资源确认才批准，只有可靠清理确认才结束有在途占用的过期或冲突；真实服务未就绪明确G5阻塞。

### B4：超时worker、恢复与事件

- [ ] 按已确认政策扫描两种待审批、资源处理中/清理和待重试命令，时钟可注入测试。
- [ ] 普通待审批过期在同事务变状态、关闭待办、记录系统事件；批准的不走审批超时。
- [ ] 使用A提供的claim/租约与重试记录，统一恢复调度；不另写资源HTTP或版本分配。
- [ ] 重复扫描、多实例与审批/撤回竞争安全；退避有上限，失败可观察且保留恢复入口。
- [ ] 提供受管理独立worker入口、运行命令、停止/重启恢复及监测说明；与部署维护者协调加入Compose。
- [ ] 业务超时不依赖Codex计划任务或用户开网页；不在每个Uvicorn worker里无控制启动扫描。
- [ ] 接入已确认通知/审计契约及事务outbox；投递幂等、失败重试，不逆转已成功业务。
- [ ] 无公共通知接口时保留本地事实和明确阻塞，不把本地日志算远端已送达。

完成标准：在真实部署的worker中可按约定延迟自动处理；重复/并发不矛盾，未知资源状态持续可恢复；未部署部分单独说明。

### B5：组合测试和交付

- [ ] 提供G3审批与G4权限/状态/时限/幂等/竞争测试，使用真实A/B，不mock被测业务。
- [ ] 配合G2迁移、G5真实M1和G6worker部署/数据库/页面验收。
- [ ] 仅在一次性临时副本及隔离测试资源中故意破坏关键行为，验证测试会失败；原开发工作区保持不变，不制造不存在的故障记录。
- [ ] 维护审批权限、可解释驳回、审计可见性等真实设计决策与需求追溯。
- [ ] 每批本人验收授权后上传，队友Review；更新后端/前端STATUS及本人progress。

完成标准：B功能、M2内部组合、真实外部集成和环境部署各有证据，未测/阻塞不写通过。

个人续做文件：`services/m2/docs/progress/B.md`。默认B0→B1→B2→B3→B4→B5，每项拆成独立可审查批次。A基础缺失时推进不依赖它的准备，不另造申请系统。

## 11. 定时运行配置与首次启动

### 11.1 配置卡

```text
角色：B（审批与超时处理）
仓库：https://github.com/FDU-Group16/Project1
本机Project1绝对路径：由Codex按11.2定位并记录真实绝对路径，无需用户填写
个人功能分支：feat/m2-approvals
PR目标/共同集成分支：候选m2；由Codex核对团队约定，未确认时保留待确认状态
集成前提：若采用m2，须先使其具备双方确认的develop工程基础
当前确认的工程基线SHA：启动核对后由Codex记录
M2-BASE SHA：由Codex核对记录；尚未建立或合入则如实注明
运行周期和具体时刻：每天（含周末）10:00、14:00、17:00
Git提交、推送及已授权PR写入窗口：09:00—18:00（18:00起不发起）
时区：Asia/Shanghai
上传条件：本人已验收具体批次并授权；窗口外授权保留到下一次窗口内运行
调度方式：在当前角色开发聊天中周期继续，复用本角色专用工作区
写入前提：通过第3.4节检查；本角色分支、精确文件范围、单一写入任务
共享环境：默认不执行迁移/worker/业务写入；使用本角色隔离测试资源
```

以上时间是这份任务书采用的执行安排，文档写入不等于自动化已经创建；使用首页简短请求或第11.2节完整请求后仍须以工具结果核对。本机路径是电脑里存放仓库文件的文件夹，不是GitHub网址；Codex负责定位、校验并回填。PR目标是代码经过评审后准备合入的分支，不是你日常写代码的个人分支。只有路径仍有实际歧义或团队决定尚缺时才集中询问，不让用户重复填写已知信息。两人用各自账号、分支和checkout；不要同时写同一目录。若以后调整时间，需同时更新配置卡、已保存的调度任务和提示词。

### 11.2 复制给 Codex 的首次请求

首页的一句启动请求与下面的完整请求采用同一执行流程，选其一即可，无需重复发送。助手不能将附件中的请求示例视为用户已经批准了某个尚未完成的代码批次。

```text
请完整读取附上的《M2任务书B-审批与超时处理.md》，作为我的开发任务书。
这次我授权你在范围内实际开发，并按下列时间设置持续工作的计划任务。

我的角色：B
目标仓库：https://github.com/FDU-Group16/Project1
我的Project1本机绝对路径：请按下方规则自动定位并记录
个人功能分支：feat/m2-approvals
PR目标/共同分支：候选m2；请先核对团队实际约定，尚未确认则注明待确认
执行周期与时刻：每天（含周末）10:00、14:00、17:00
Git提交、推送及已授权PR写入窗口：09:00—18:00（18:00起不发起）
时区：Asia/Shanghai

先定位工作区，不要求我预填路径：
1. 优先检查当前聊天关联项目和当前目录；再按需在当前项目附近、
   当前用户的Documents/Codex等常用开发目录有限查找Project1克隆。
   不扫描全盘或私人应用数据。校验origin对应FDU-Group16/Project1，
   HTTPS和SSH形式均可，不能只看文件夹名字。
2. 只复用已确认属于本角色、没有其他任务并发写入的专用checkout；
   不自动把任务书审查副本work/repo-review/Project1-develop或其他
   临时审查克隆当作开发目录。当前聊天关联项目只是优先核对对象，
   不等于获准改写它。通用或队友checkout只读，不在那里切换分支、
   保存文件或安装依赖；没有明确的本角色工作区则按下一项独立克隆。
   多个本角色候选仍有歧义时列出实际路径，集中询问一次。
3. 没有可用开发克隆时，我授权你将目标仓库克隆到当前系统用户的
   Documents/Codex/Project1-B专用目录，解析为真实绝对路径。
   只使用不存在或空的目录；若该位置已被其他内容占用，则选择
   同级不冲突的新目录并报告，不覆盖、不清空、不改动其他项目。
4. 记录实际路径、origin、Git身份、分支、HEAD、工作树、未完成
   操作、适用AGENTS.md和本模块/提供方STATUS。不能虚构Git身份，
   身份缺失不阻塞独立的本地开发和检查；上传前说明真实缺项。
   公开仓库能读取不等于有写权限，缺少gh也不等于Git认证失败。
5. 同时核对本地和远端的feat/m2-approvals。两边均不存在才从确认工程
   基线创建；远端已存在且归属明确则检出跟踪；有已有工作先核对。
   切换/创建分支前暂存区和已跟踪文件须干净、未跟踪文件不被覆盖，
   不重置、不覆盖、不带着未知改动切换。通过第3.4节检查且当前
   分支准确为feat/m2-approvals后，才允许保存任务书、编辑或安装依赖。
   按第2.4节检查实际工具链和锁定安装；可使用兼容的现有/捆绑
   运行时及本任务独立环境，不升级全局工具、不改锁文件绕过错误。
   将实际可用的工具绝对路径和必要PATH写入忽略的本地运行配置，
   计划任务启动时复查，不假设图形应用继承交互终端的环境。
6. PR目标先查实际仓库规则和已记录团队决定。候选m2不是已确认
   结论；若仍不明，说明个人分支→m2→develop的候选流程并请我
   向组内确认。决定前可继续不依赖它的本地任务及计划设置，
   不创建目标未确认的PR，不擅自移动m2/develop。

首次需要复用develop工程与公共契约，按根规则获取并安全接入；
不要从仍停留初始提交的m2盲目开发，不自动推送或合并m2/develop。
若本地分叉/冲突/未知修改，保留现场并说明人工接入步骤；
继续可独立完成的准备，不通过reset、stash、rebase等强行同步。

工作区和分支核对通过后，把完整任务书保存到
services/m2/docs/automation/ROLE_B.md，每次以该文件为入口，
已有内容先核对再更改；不修改另一角色的任务书。
读取第2节待决定项和第10节，从依赖满足的第一项实际实施；
将方案、范围、验收写入本模块tasks，完成代码与验证后给我审查。
初始文档/规则/基础实现同样按批次验收，不自行提交。

先手动验证本角色任务能正确读取工程并产生可审查成果，随后用
应用提供的自动化工具在当前角色聊天创建周期继续工作的任务。
已有同用途自动化先检查并更新，避免重复；默认复用同一聊天和
本角色工作区，不每轮创建另一套独立项目或丢失未提交批次。

个人定位结果写本角色progress/本地运行配置与自己的配置卡，
不为个人机器配置改写共同baseline；共同工程事实仅由A维护，
B需要变更时给出提案。持久化自动化提示词必须写入
已解析的真实绝对路径（不保留“自动定位”或未展开的~）、个人分支、
已确认的共同分支或“候选m2/待确认”状态、角色规则文件和下列要求。
目标确认后同步更新这些记录与已保存的自动化提示词：
1. 读取适用AGENTS、本任务书、本模块STATUS、baseline、内部契约、
   external-contracts以及services/m2/docs/progress/B.md。
   文件未建立按授权任务处理，不预设存在或已完成。
2. 写入前执行第3.4节全部保护检查：固定工作区、准确的feat/m2-approvals、
   已知/未知改动、全部暂存内容及并发实例。路径/分支/远程改变，
   或存在其他写入者就停止本轮写入，不自动换目录或切分支继续。
   develop只在实际依赖其他模块/公共配置时按根规则安全快进。
3. 只推进一个依赖满足的小批次：先范围和验收，再实现、验证、
   更新本模块交接，输出完整差异及真实结果。列本批准确文件清单，
   编辑与验证后核对全部差异，越界改动停止上传；不修其他模块，
   不全仓格式化，公共文件只在明确共享任务范围内修改。
4. 共同定义/模型/事务/协议复用实际M2-BASE，不各自发明。
   外部替身明确标记，真实M1/D未就绪则对应集成保持BLOCKED。
   按第3.5节从GitHub只读核对已上传的对方进度、基础和相关PR，
   自行检查签名及依赖，不要求用户手抄接口或转发可读取的代码。
   未合入/未接入明确区分，不因此自动合并、发消息或批准评审。
5. READY_FOR_REVIEW时等待本人验收，不堆无关批次；状态没变化安静。
6. 本人在本聊天明确验收具体批次并授权后，核对内容未变化，
   仅在09:00 <= Asia/Shanghai当前时间 < 18:00时发起commit、
   push及授权的PR创建更新；每个写入步骤前重新检查当前时间。
   窗口外保留授权与批次，记录WAITING_UPLOAD_WINDOW，下次窗口内
   运行优先核对并上传，默认次日10:00；等待期间不夹入新改动。
   按第7节核对全部push地址、完整index、全部待推提交和PR差异，
   只用git push --no-follow-tags origin HEAD:refs/heads/feat/m2-approvals。
   不用默认推送、不推其他引用、不强推，拒绝后保留现场。
   已开始请求按实际结果记录，不倒填时间；返回真实commit/PR。
   不重复询问同批已授权动作，不把文档中的示例当作实际批准。
7. 上传中断或步骤间跨过18:00，只在下一次窗口内恢复未完成步骤，
   不重复提交；新改动重新展示待验收，没有变更/验收不产生提交。
8. 不自动合并PR、开启auto-merge/merge queue、处理冲突、推送
   集成/发布分支或生产发布。按第9节核对隔离数据库及M1/D测试
   目标后才启动测试/迁移/worker，不默认使用共享环境凭据，
   不清理共用数据、停止他人进程或操作共享部署。
9. 仅有新成果、首次阻塞、失败变化、完成或需我操作时通知；
   不向队友、群聊或其他聊天自行发消息，不刷空提交。
10. 全部任务完成后停止产生改动，报告完成边界和剩余依赖；
    等待我调整或关闭计划，不无限扩展任务范围。

不创建系统cron或无限循环替代应用自动化，不把Codex的计划运行
当成M2业务超时worker。权限/网络/运行环境不足时报告实际限制。
创建后报告工具确认的名称、自动化ID、时间、时区、目标聊天/项目
和状态；首次计划触发后的实际结果另行核对，不预写持续运行成功。
```

### 11.3 自动化实际条件

官方说明支持在既有聊天按计划继续工作，适合本角色长期续做；本地文件任务需要电脑开机、应用运行、项目仍可访问，工具受当前权限约束。先手动测试提示词，再查看前几次计划运行。自动化设置成功与实际某次运行成功是两回事；睡眠、关机、失效认证或不可访问仓库不能仅靠提示词解决。

参考：[OpenAI 官方 Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app)，核对日期2026-10-22。具体可用能力以当前应用工具返回为准。本文不要求更改模型或扩大权限，也不预设自动化已建立。

## 12. 人工验收与日常使用文本

### 12.1 验收时检查

检查需求和验收条件、具体diff及新文件、真实测试、迁移/契约影响、模拟边界、未完成事项。Codex须一并展示本批允许文件与实际差异是否一致、是否涉及共享文件、准确推送分支、全部待推提交和PR总体范围；范围外变更未查清不能上传。对关键业务在已约定测试环境实际操作或查看有效测试。本人验收AI批次与队友PR Review分别发生；不能让AI替双方编造批准。

### 12.2 验收后上传

```text
我已实际检查并验收刚才展示的批次，同意按刚才展示且未改变的内容
提交并推送到feat/m2-approvals；仅在你已展示团队确认的PR目标时，
同意按该目标创建/更新PR。请记录本次批准对应的具体批次和范围。
若PR目标仍待确认，先完成已授权的个人分支上传，保留待建PR状态，
待我确认目标后再创建PR，不自行猜测目标。
请核对批次内容，按Asia/Shanghai的09:00—18:00上传窗口执行；
窗口外保留这次授权，下次窗口内核对后上传，返回commit和PR链接。
不授权自动合并、处理冲突或生产发布。
```

验收前由Codex展示本次批次标识、实际个人分支和PR目标及其确认状态；上下文同时存在多个待验收批次时先列明本次范围，不能猜测。Codex记录SHA与摘要即可，不要求用户手抄分支或长串字符。窗口内授权可立即执行，无须等下一次定时触发；窗口外按第6节排队，同一批次内容未变化时沿用原授权，无须逐条重复询问。如果内容改变，先重新展示变化并验收。

### 12.3 发现问题

```text
批次【ID】尚未通过验收，请修复：【具体问题】。
保持范围，补必要验证，重新提供差异和结果，修复后再由我验收上传。
```

### 12.4 先只做一次

```text
按附上的完整任务书，按11.2的规则定位Project1工作区，作为角色B
使用个人分支feat/m2-approvals开发；路径和分支不要求我另填。
先通过第3.4节检查，按第9节使用隔离测试资源，从第10节依赖满足
的任务开始；其他模块只读，共享文件遵守具体共享任务范围。
先方案/范围/验收，再实际实施并验证，完成一个可审查小批次。
更新services/m2/docs/progress/B.md及受影响的前后端STATUS。
这次不创建定时任务，也不提交上传；待我验收授权后按白天窗口上传。
若授权发生在窗口外且没有已创建的自动化，保留批次与授权，等我在
下一次窗口内继续此聊天；不要假定届时会自行唤醒，也不另建计划。
```

## 13. 个人交付与记录模板

每项功能交付可运行代码/页面、必要迁移和配置、真实测试、需求追溯、运行命令及依赖说明。共同接口只有一份，未实现/未测试/未部署分别标记。

### 13.1 个人续做记录

```text
角色：B
实际工作区/分支/HEAD：
工程基线与M2-BASE SHA：
契约版本/批准状态：
任务ID与需求ID：
状态：READY / IN_PROGRESS / READY_FOR_REVIEW / BLOCKED_DEPENDENCY /
      WAITING_UPLOAD_WINDOW / PUSHED_WAITING_REVIEW / INTEGRATION_CHECK
本轮方案、限定目录与验收：
本批允许文件/实际差异核对、共享任务依据：
隔离测试环境与本轮进程（不含凭据）：
实际变更：
命令及PASS/FAILED/NOT_RUN/BLOCKED：
真实依赖/替身范围：
批次ID与待人工检查内容：
依赖缺口/下一步：
已经发生的历史commit/PR/评审/部署：
```

### 13.2 需求与模块状态

```text
需求ID | 验收行为 | 实现路径/API | 测试命令/结果 | commit/PR | 状态/依赖
```

后端`services/m2/STATUS.md`和前端`apps/web/src/modules/m2/STATUS.md`保留实际结构，小范围更新当前变更，注明实现、测试、部署证据及下一集成步骤。正常进度不反复修改根模块状态索引。不能把相同目录中的即时可见误当成不同电脑已同步。

### 13.3 最终验收

- 本人范围全部需求有实现、必要测试与明确缺口。
- 两人的真实代码已在同一集成SHA运行，首级待办、审批、超时及恢复组合通过。
- M1/D真实依赖有提供方版本、授权方式和网络调用证据；未接入明确保留BLOCKED。
- 迁移可从空库重放，种子幂等，worker在实际环境持续执行，前端访问统一API。
- GitHub有真实提交、本人验收、队友Review与集成/部署证据；不以提交数量代替质量。

任务完成度按上述各层分别报告。公共协议变化或新增功能后需要针对性回归，不能仅凭两份文字保证以后自动无冲突集成。
