# M2 工程基线

核对日期：2026-10-24。已整合A0-01/B0历史；A0-02仅实现Actor/TimeRange，完整M2-BASE及业务政策尚未成立。

| 项目 | 证据/状态 |
| --- | --- |
| 仓库 | https://github.com/FDU-Group16/Project1 |
| 实际工程基线 | develop@99ce858a2bbf8caa2f4b226a83f989c54d6992d1，首次显式fetch成功，本地已检出 |
| 本次上传目标 | 用户明确授权本次直接上传m2；已fetch到e307d29b1470ca5ec889c6c18a9096d4080cc479并在本地fcdb86c无冲突整合，保留A/B历史。m2已含工程基线，不再落后13提交；上传结果以实际远端为准 |
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

- contracts.py：Actor、TimeRange及输入校验已实现；其他DTO/枚举/Protocol未实现。行为测试见tests/test_contracts.py；签名见 [内部协议](contracts.md)。
- db.py / uow.py：唯一Base、Session工厂、用例事务，待技术/schema决策。
- state.py / application_models.py：合法状态与申请/幂等/命令，待政策及数据方案。
- resource_commands.py：版本、持久化命令、claim/续租/回执/重试，待共同签名评审和数据库。
- migrations/：单链迁移，尚无revision/head；B新增迁移必须先协调parent。
- composition.py：待真实实现就绪再装配；不导入不存在的B文件。

## 下一步与证据门禁

A0-01已由本人验收并上传；本次按新的明确授权将A0-01和A0-02整合后直接上传m2。团队确认 [决策清单](decisions/A0-01-proposals.md) 中具体数据库依赖/隔离配置后，后续落实Base/UoW/模型；业务政策未确认部分继续阻塞。B核对签名和事务边界；基础经评审集成后双方记录同一实际SHA再组合。

G0只证明骨架可检查；G1当前只覆盖静态契约；G2～G6均未完成。共享检查当前不自动读取M2新契约，不自动运行未来M2测试。
