# A 续做记录

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
