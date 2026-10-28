# A 续做记录

## 最新记录：2026-10-28 A1-02（READY_FOR_REVIEW）

- 用户要求把10月29日开发提前到今天。本批已在原A专用目录/m2完成；10月29日全天跳过定时开发，10月30日起沿用10:00、14:00、17:00；待验收期间冻结不叠加。自动化m2-a已保存当日跳过规则，非永久暂停。
- A1-01已按用户技术验收上传授权于今天12:27:54普通推送734cc271cc833cef822aae2819f22af9c472c845，独立API核实；原待验收描述为历史。本批开工API仍同SHA，未见新增B交接。本次只授权本地开发，无A1-02提交上传授权。
- A1-02核心保存防重：请求键/规范化摘要持久化、同键回放、内容冲突、用户隔离、数据库并发仲裁、申请与键同事务。独立内部作用域，不冒充正式提交或通用202回执。精确12文件及设计见[任务](../tasks/A1-02.md)。
- 68项PASS（28项真实PG，无skip），双连接真实阻塞场景和失败回滚通过，关闭摘要判断的隔离副本正确失败；root check PASS。首轮实际67测试通过，但验证脚本预期数误写68而退出；随后补充跨owner损坏关联的拒绝泄露测试，最终68项和后续迁移检查/故障注入均通过，未放宽断言。
- 私有PG复用原data/0600配置，无provision/新安装。只upgrade至0003_creation_keys，验证旧申请不变、重复upgrade、alembic check。未运行任何旧降级脚本；最终applications/application_creation_keys均0行、服务停止/socket移除。以后复验仅按归属/空闲端口确认后恢复原实例、专用配置和unittest，结束停止本人实例。
- .git/m2-a/A1-02-manifest.json与A1-02.patch保存精确范围/hash，runtime READY_FOR_REVIEW；index空，不stage/commit/push。根依赖/公共文件/B文件未改，无PR/部署/队友Review。明天只展示现有成果，真实身份、房间校验、正式提交和审批集成未完成。

## 以下为历史续做记录

## 最新记录：2026-10-27 A1-01（READY_FOR_REVIEW）

- A0-05已由代理按用户明确授权技术验收并普通推送7a95ca4a8e507060d6fedf40486168827839b7ff，GitHub API确认；48测试及根检查通过，无队友评审或部署。本批开工远端仍同SHA、工作树干净，无新B提交。
- 继续已授权本地开发：申请核心主表/模型注册、内部存储和本人查询，共12文件，见[A1-01](../tasks/A1-01.md)。不触发develop，不改公共文件/依赖或B目录，不赋予本批上传授权。
- 全部57测试通过（新增9项真实PG，总计17项真实PG，无skip）、无业务表base迁移重放/重复upgrade/模型无漂移、根check通过。初次故障注入误导入原包，未算有效；纠正一次性副本包路径后，删owner过滤使越权测试正确失败。副本已删除。
- 本机恢复原私有PG18，仅127.0.0.1:55432/m2_a_test库与同名普通账号、m2 schema。测试后applications0行、只余applications/alembic_version两表，head0002_applications；本轮私有服务已停止/socket移除。凭据仍0600保存在.git/m2-a/postgres18/test-env.json，不输出；勿重复provision。以后复验不运行本轮降级重放脚本；仅在按归属/端口检查后启动原data、加载专用环境，执行unittest，最后停止本人服务。
- .git/m2-a/A1-01-manifest.json及A1-01.patch记录精确范围/摘要；本聊天outputs/A1-01验收说明.md及完整diff/测试日志供审查。未stage/commit/push，等待本批验收授权；不叠加新批次。
- ApplicationData只是核心数据，不是已提交业务申请或公开ApplicationView；尚无状态/version/审批路由/截止、持久幂等/审批接口/HTTP、真实D/M1/B组合。下一步先验收上传本批，再按已评审政策/接口补正式提交原子性，不能将私有存储测试当正式业务已可用。

## 以下为历史记录

## 最新记录：2026-10-26 A0-04（READY_FOR_REVIEW）

- 用户要求今天继续实际开发；完成请求作用域与规范化输入摘要，精确8文件见[任务](../tasks/A0-04.md)。本批未stage/commit/push，没有本批上传授权。
- 工作区仍为A独立目录，分支m2。写入前保护检查通过并持A锁；远端出现B接口评审29d0f5b66505475298c9ec89b4017299620c2d50，已完整读差异并从干净e1bae59安全快进，无冲突/历史改写；不触发develop同步。
- A0-03已经按用户授权于2026-10-25 13:01完成技术检查并上传e1bae596679a9107905a96dde3a8008110acf1de。下方旧待验收内容为历史，不伪造用户亲自测试或队友评审。
- 新增10项测试，共35项M2单测通过；忽略人数的临时故障注入被测试发现；根check.sh及本地演示通过。没有新依赖/公共配置/数据库/M1/D写入，没有替身、B代码改动或部署。
- B已上传两项技术评审：ApprovalPort初始化可信快照、save_result之后未编排回执的持久恢复入口；未定稿、不据此批准业务政策。本批请求摘要独立于这两项。
- 下一阶段为明确SQLAlchemy/Alembic/驱动限定依赖任务、独立PostgreSQL准备与Base/UoW；不得把请求摘要称为已实现并发防重或申请保存。日期目标仍为10月29日部分成果。

## 历史记录：2026-10-24 A0-03（提交前快照）

- 用户已明确删除个人分支；A专用工作区不变，当前分支m2。上午成果已推送m2@`1ad9fd08fee456dd4fd9cd706bf8ac9215f09743`，本轮远端核对同SHA，未发现新增B提交。下方旧分支/待上传描述保留为历史。
- 新增ApplicationCreate输入校验及11项行为/契约测试，全部M2单测25项、故障注入检查和根check.sh通过。此前一次长度边界测试把两个汉字重复500次误当500字符，修正测试数据后通过，未放宽校验。
- 本批10文件完整范围见[任务](../tasks/A0-03.md)。未修改B文件/前端/公共契约/依赖锁，未注册API或连接数据库，仍无申请落库/真实身份/审批能力。
- 状态READY_FOR_REVIEW：未提交未上传，等待用户实际验收本批；上午上传授权不扩展到本批。完整diff与文件摘要保存在本地运行记录及验收输出。
- 下一步仍是具体数据库依赖与独立测试库准备、Base/UoW及申请持久化；需要团队确认的审批政策继续保持proposed，不借DTO校验默认批准。

## 历史记录：2026-10-24 A0-02

- 本地开发仍在本人 `feat/m2-applications`。用户2026-10-23明确授权本日开发自检后，将A成果直接推送`m2`；本次无需再次请求验收上传许可、不建PR。没有事后人工验收、B批准或部署的证据。
- A0-01已于2026-10-23提交并上传个人分支，SHA `3a0892119534df422f47ec1f0977c7b6462ed6c2`；下方旧记录是提交前快照，不再代表当前上传状态。
- 本日fetch `m2@e307d29b1470ca5ec889c6c18a9096d4080cc479`，包含develop工程基线和B0。已在本地`fcdb86c`无冲突整合，B四个独有文档逐字保留，STATUS保留双方记录；没有移动远端分支。A0-02上传在实际成功后由工具证据及下一记录确认。
- 本批源码：`services/m2/contracts.py`，只实现Actor/TimeRange；真实行为测试：`services/m2/tests/test_contracts.py`。任务/精确9文件范围见[任务](../tasks/A0-02.md)。
- 单测14项通过；临时副本故意引入相邻边界重叠错误，对应测试正确失败；根check.sh验证结果见任务完成记录。无共享依赖或业务规则变更，无数据库、假身份运行入口或服务替身。
- 下一依赖：具体SQLAlchemy同步风格/驱动和共享依赖变更范围、独立PostgreSQL测试库配置；B核对已落实类型并等待Base/UoW/申请接口，不自行复制。两级审批等政策仍待确认。M1/D真实业务仍未接入，下周四目标仅初期成果，不能以类型测试代替申请演示。

## 历史记录：A0-01上传前快照

角色：A。批次：A0-01（工程基线与接口评审包）。状态：READY_FOR_REVIEW。

## 工作区与版本

- 实际专用工作区：/Users/wuyufan/Documents/Codex/Project1-A（无符号链接）。
- 分支：feat/m2-applications；origin：https://github.com/FDU-Group16/Project1.git；准确推送目标：HEAD:refs/heads/feat/m2-applications。
- HEAD和已fetch工程基线：99ce858a2bbf8caa2f4b226a83f989c54d6992d1；首次显式fetch完成于2026-10-22本轮检查（Asia/Shanghai）；新分支从该基线建立，不跟踪develop以免误推。
- M2-BASE：尚未实现或合入。候选集成/PR base：m2，待团队确认；远端m2为a57193f，落后develop13提交。不得现在对旧m2建PR。
- 远端A/B个人分支未出现；GitHub已查PR #1/#2为骨架合入；无B可见业务交接。队友未上传本地状态未知。

## 本批内容与范围

需求：M2-01～03、X-02～04、E-01/02/03/05/07/09。首个可独立推进小批次为方案/接口准备。详见 [任务](../tasks/A0-01.md) 的11个精确文件；实际差异核对按该清单。只新增A局部规则、完整A任务书与配置卡、基线、内部协议、公开HTTP草案、外部依赖、待决项和运行说明，并追加M2后端STATUS。本批无前端或其他模块修改、无B实现。

公开契约：contracts/m2.openapi.json@0.1.0-proposed，9个操作，未注册；内部签名含ApplicationPort/ApprovalPort/RoomBlockPort及命令领取/续租/结果/重试。尚无共同Base/UoW/模型/业务代码。未使用替身。

## 工具与验证

- 系统默认Python 3.9.6、Node 23.11.0不作项目运行时；实际采用Codex Python 3.12.14和Node 24.19.0，npm 10.9.2在Node 24下运行，uv 0.10.0安装在本checkout.git/m2-a/tools中；项目环境为.venv。
- 绝对路径、PATH、缓存目录、重现命令与执行日志保存在.git/m2-a/runtime.json、runtime.sh、check.log；无凭证。每轮重新核对。未修改全局PATH或全局Git配置。
- PASS：uv sync --frozen（显式Python 3.12）、npm --prefix apps/web ci；根依赖/锁文件内容未改变。
- PASS：bash scripts/check.sh，M1契约2操作/引用、Python编译、真实四服务本机健康响应、Vue类型检查、生产构建。
- PASS：FastAPI OpenAPI模型校验；本批草案9操作/本地引用/幂等和202声明结构检查；允许文件/Markdown链接及diff空白检查。静态校验不等于业务服务通过。
- G2～G6：BLOCKED/NOT_RUN。没有M2数据库、真实A/B组合、外部业务联调或部署验证；本轮未连接任何数据库/M1/D业务，不运行迁移或worker。
- npm audit报告既有vite 8.2.0高危告警（1个包，多个advisory），交公共维护者另列依赖修复任务；本批不改共享锁。

## 验收、自动化与下一步

本人尚未验收/授权本批上传；无提交、推送、PR、队友Review或部署。当前远端个人分支不存在，从确认基线算本方新提交数为0；将来只能上传本人已验收增量。按用户本轮明确指示仅在本仓库配置Git署名kswyf426、邮箱yufanwu468@gmail.com；GitHub用户名yufanwu-111。gh未安装；Git写权限/PR认证尚未验证，公开克隆成功不等于可写。

A自动化的真实ID、时间、提示词、状态写入本地.git/m2-a/runtime.json及当前聊天工具结果，避免把未来结果预写入版本文件。固定本聊天与专用工作区，每天Asia/Shanghai 10:00、14:00、17:00；READY_FOR_REVIEW保持安静，不叠加新批次。首次定时触发另查实际结果，创建成功不代表已经触发。B自动化不创建。

待团队确认见 [决策清单](../decisions/A0-01-proposals.md)。B只需评审共同签名/事务、领取租约和恢复场景，再按自己的B0/B1实施；不需要B整套实现才能验收本批。下一批在本人验收当前批次及相关方案确认后推进共同类型/UoW，不把待决政策写成正式业务。

## 用户本轮补充边界（2026-10-22）

A/B分支分别为feat/m2-applications、feat/m2-approvals；m2基线由用户与队友协调同步，代理只检查差异/提供步骤。审批政策继续待组内确认。用户同意按SQLAlchemy+Alembic+PostgreSQL准备，A共同基础/B按接口接入，使用独立测试库；同步风格/schema账号/共享依赖和配置的具体变更仍待确认。未授权操作共享数据库或推送/合并m2、develop、main。对接人暂待组内确认，协调清单见决策文件。此回复不是本批最终验收上传授权。


## 2026-10-27 A0-05 本地实施

用户回复“就按这个来”，批准本批技术/共享依赖/本机私有测试范围；上传须另验收授权。准确范围与验收见 [A0-05](../tasks/A0-05.md)，仍在原 A checkout 的 m2@13bb317667ebb1dc0f3fd5180e9e4c99ff89be3d，持本人运行锁编辑验证；A0-04已上传，不重做。

重试 fetch 已确认 origin/m2 同 HEAD，origin/develop@99ce858是祖先；无快进/合并需要。共享依赖仅增加 SQLAlchemy、psycopg binary、Alembic与必要传递包，既有版本不升级；沿用 unittest。现有 Node 本轮复查为24.22.1，Python为3.12.14、uv0.10.0，不升级全局工具。

本机私有集群拟放 `/Users/wuyufan/Documents/Codex/Project1-A/.git/m2-a/postgres18/data`，127.0.0.1:55432，m2_a_test库/m2 schema/同名业务账号；另用独立bootstrap管理员初始化。密码只放忽略配置并设0600，不提交或展示。安装预检需升级ca-certificates，用户明确“允许仅升级 ca-certificates”；已完成安装，实际既有包仅该证书包变化，其余为新依赖。PostgreSQL 18.6；未使用brew services。

当前48项测试全部通过（含8项真实PG，无跳过）、一次性副本回滚故障注入有效、根check通过。状态READY_FOR_REVIEW，未stage/commit/push；不叠加新批次。初轮测试将inet地址转文本得到127.0.0.1/32，已改用PostgreSQL host()取地址再严格等值核对，未放宽隔离条件。

数据库验收完成于2026-10-27 12:14（Asia/Shanghai）；私有集群/data及0600秘密配置保留在.git/m2-a/postgres18，本轮进程已停止，临时socket目录已移除。复验需先恢复socket目录（路径在该目录socket-path文件，0700权限）再pg_ctl启动该明确data；不重新initdb或执行provision覆盖已有集群。测试读取test-env.json中的专用环境变量（勿输出其内容），命令为`.venv/bin/python .git/m2-a/A0-05-verify.py`，结束只停止该data对应进程。最新本轮远端只读查询超时，不能以更早成功fetch冒充当前最新；上传前重新核实m2。
