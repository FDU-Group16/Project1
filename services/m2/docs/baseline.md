# M2 工程基线

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
