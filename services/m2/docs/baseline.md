# M2 工程基线

核对日期：2026-10-22。工程事实已核对；M2共同实现与团队决定尚未成立。

| 项目 | 证据/状态 |
| --- | --- |
| 仓库 | https://github.com/FDU-Group16/Project1 |
| 实际工程基线 | develop@99ce858a2bbf8caa2f4b226a83f989c54d6992d1，首次显式fetch成功，本地已检出 |
| 候选集成分支 | m2@a57193fd3e1ba5c411333b07ebb62b1419635fcb，落后13提交；流程与基线同步待集成人确认 |
| M2-BASE | 尚无已实现/已合入SHA；A0-01只是工作区接口准备 |
| M2入口 | services.m2.main:app，仅GET /healthz |
| Web入口 | apps/web/src/modules/m2/routes.ts，仅静态/m2 |
| 工程工具 | Python 3.12；CI Node 24、uv 0.10.0；根uv锁与Web npm锁 |
| 当前数据能力 | Compose配置PostgreSQL 18；无M2业务schema/账号/迁移 |
| M1协议 | contracts/m1-room-blocks.openapi.json，0.1.0-proposed，提供方未实现 |
| M2公开协议 | contracts/m2.openapi.json，0.1.0-proposed，本批草案，未注册 |
| GitHub协作 | 本次查询个人A/B分支均不存在；PR #1/#2均为已合入develop的骨架工作，无B业务交接 |

个人机器配置只存个人progress和本地元数据，不作为共同工程要求。

## M2-BASE 的拟议文件与实现状态

- contracts.py：共同DTO、枚举与Protocol，尚未实现；本批签名见 [内部协议](contracts.md)。
- db.py / uow.py：唯一Base、Session工厂、用例事务，待技术/schema决策。
- state.py / application_models.py：合法状态与申请/幂等/命令，待政策及数据方案。
- resource_commands.py：版本、持久化命令、claim/续租/回执/重试，待共同签名评审和数据库。
- migrations/：单链迁移，尚无revision/head；B新增迁移必须先协调parent。
- composition.py：待真实实现就绪再装配；不导入不存在的B文件。

## 下一步与证据门禁

A0-01由本人验收后可上传个人分支供评审；不以B完整实现或G3作为准备批次上传前提。团队确认 [决策清单](decisions/A0-01-proposals.md) 后，下一小批次落实共同类型和UoW。B核对签名和事务边界；基础经评审集成后双方记录同一实际SHA再组合。

G0只证明骨架可检查；G1当前只覆盖静态契约；G2～G6均未完成。共享检查当前不自动读取M2新契约，不自动运行未来M2测试。
