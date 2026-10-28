# M2 工程基线

## 当前基线：2026-10-28 A1-02

A1-01已上传m2@734cc271cc833cef822aae2819f22af9c472c845，本批开工GitHub REST确认同SHA；B最新已上传交接仍为10月26日接口评审。纯M2内部任务，不触发develop同步，未移动分支。

本地A1-02增加ApplicationCreationStore/ApplicationSaveResult/ApplicationCreationConflict及ApplicationCreationKey。
唯一迁移链为0001_m2_schema → 0002_applications → 0003_creation_keys；Base/Session/UoW及旧申请表保持一份。
只在READ COMMITTED内部事务保存核心申请和创建键，用四字段唯一约束及SAVEPOINT避免并发重复。
没有完整ApplicationPort、工作流状态、正式装配或公开HTTP业务接口；独立core-create-v1作用域不得冒充正式提交成功。

68项测试通过（28真实PG），旧申请迁移保留、重复upgrade/无漂移、摘要故障注入和根check通过。
本批尚未提交上传/团队评审/部署，后续B迁移以实际接入并确认的head衔接，不能把本地文档当远端已有。
范围/兼容边界见[A1-02](tasks/A1-02.md)与[内部协议](contracts.md)。

## 以下为历史基线快照

## 当前基线：2026-10-27

已上传的A0-05为m2@7a95ca4a8e507060d6fedf40486168827839b7ff，本轮GitHub ref API确认远端同SHA；B最新已上传接口评审仍为29d0f5b。纯M2任务不触发develop同步，没有合并或移动分支。

本地A1-01在该SHA之上实现唯一Application核心数据表/模型、ApplicationStore和本人详情/分页，待验收未上传。唯一Base/同步Session/UoW沿用已批准技术；迁移链0001_m2_schema→0002_applications，实际私有PG18验证57项测试和工程检查通过。B后续迁移须以真实已接入head为parent，不依据本地待验收文档自行复制模型。

存储快照不是ApplicationView，尚未加入审批状态/截止/version/路由或正式装配；无正式提交、幂等回放、真实B/M1/D组合。政策保持proposed，不把本地技术验证视为队友评审或部署。详见[A1-01](tasks/A1-01.md)。

## 以下为历史基线快照

核对日期：2026-10-26。A0-01～03已上传，B接口评审已同步；A0-04本地请求摘要和作用域待验收。完整M2-BASE及业务政策尚未成立。

| 项目 | 证据/状态 |
| --- | --- |
| 仓库 | https://github.com/FDU-Group16/Project1 |
| 实际工程基线 | develop@99ce858a2bbf8caa2f4b226a83f989c54d6992d1，首次显式fetch成功，本地已检出 |
| 当前工作与上传分支 | A按用户最新指示在专用目录的m2开发，个人分支已删除；A0-01/02已上传m2@1ad9fd08fee456dd4fd9cd706bf8ac9215f09743，本轮远端同SHA。A0-03仅本地待验收 |
| M2-BASE | A0-02已实现可导入Actor/TimeRange；没有Base/Session/UoW/模型/迁移/port/装配，不能称共同基础完整 |
| M2入口 | services.m2.main:app，仅GET /healthz |
| Web入口 | apps/web/src/modules/m2/routes.ts，仅静态/m2 |
| 工程工具 | Python 3.12；CI Node 24、uv 0.10.0；根uv锁与Web npm锁 |
| 当前数据能力 | Compose配置PostgreSQL 18；无M2业务schema/账号/迁移 |
| M1协议 | contracts/m1-room-blocks.openapi.json，0.1.0-proposed，提供方未实现 |
| M2公开协议 | contracts/m2.openapi.json，0.1.0-proposed，本批草案，未注册 |
| GitHub协作 | A0-01已上传个人分支3a08921；B0已上传m2@e307d29。B的方案/测试设计已读取，无审批业务代码。A0-02无PR授权或评审/部署证据 |

个人机器配置只存个人progress和本地元数据，不作为共同工程要求。

## M2-BASE 的拟议文件与实现状态

- contracts.py：Actor、TimeRange已上传；ApplicationCreate输入DTO本地已实现待验收；其他DTO/枚举/Protocol未实现。行为测试见tests/test_contracts.py；签名见 [内部协议](contracts.md)。
- db.py / uow.py：唯一Base、Session工厂、用例事务，待技术/schema决策。
- state.py / application_models.py：合法状态与申请/幂等/命令，待政策及数据方案。
- resource_commands.py：版本、持久化命令、claim/续租/回执/重试，待共同签名评审和数据库。
- migrations/：单链迁移，尚无revision/head；B新增迁移必须先协调parent。
- composition.py：待真实实现就绪再装配；不导入不存在的B文件。

## 下一步与证据门禁

A0-01已由本人验收并上传；A0-01和A0-02已按明确授权整合上传m2。本批A0-03未提交未上传。团队确认 [决策清单](decisions/A0-01-proposals.md) 中具体数据库依赖/隔离配置后，后续落实Base/UoW/模型；业务政策未确认部分继续阻塞。B核对签名和事务边界；基础经评审集成后双方记录同一实际SHA再组合。

G0只证明骨架可检查；G1当前只覆盖静态契约；G2～G6均未完成。共享检查当前不自动读取M2新契约，不自动运行未来M2测试。

## 2026-10-26 最新同步与A0-04

本地m2从干净e1bae596679a9107905a96dde3a8008110acf1de安全快进至已核实origin/m2@29d0f5b66505475298c9ec89b4017299620c2d50，无合并提交或文件冲突。此为本批base；上表原A0-03待验收描述保留历史，实际已上传。

ApplicationCreate已可从m2导入；本地新`idempotency.py`提供结构化幂等作用域及版本化输入摘要，35项M2测试和工程检查通过，未上传。不是持久幂等服务，无数据库表/事务/原结果回放。B最新提交只有接口评审，没有新增B业务代码。审批初始化可信快照与资源回执持久恢复入口需后续接口批次处理；数据库技术/隔离条件和业务政策仍待确认。


## 2026-10-27 A0-05 技术决定与实际边界

A0-04 已于 2026-10-26 17:26 普通推送 m2@13bb317667ebb1dc0f3fd5180e9e4c99ff89be3d。本批在该 SHA 本地开发。开工首次网络 fetch 阻塞后结束自有查询，重试成功 fetch：origin/m2 同 SHA，origin/develop 为 99ce858a2bbf8caa2f4b226a83f989c54d6992d1，已经是 HEAD 祖先，无需切换/合并。B 最新已上传交接仍为 29d0f5b 的接口评审；不能推断 B 未上传的本地进度。

用户确认 A0-05 的同步 SQLAlchemy/psycopg/Alembic、根依赖限定变更和 A 私有 PostgreSQL 测试范围，覆盖旧 DEC-07 的本地技术待定部分；不是全组政策或 B 评审。新增本地 db.Base、Session 工厂、显式提交 UoW 与 0001_m2_schema 迁移，尚未上传；已在独立 PostgreSQL 18.6 通过 48 项测试（含 8 项真实数据库测试）与回滚故障注入、根工程检查。测试实例已停止，无业务数据或部署。M2-BASE 仍缺业务模型、port、正式装配及真实 A/B 组合，不能写整体完成。
