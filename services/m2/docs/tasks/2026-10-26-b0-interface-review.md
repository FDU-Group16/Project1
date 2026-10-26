# B0-02：共同审批接口与恢复入口评审

日期：2026-10-26（Asia/Shanghai）
状态：技术自检通过；提交与上传以实际 Git 结果为准

## 协作需求与同步

- 本批只评审已在 `m2` 的 A 侧 M2 代码和提案，不调用 M1、D，也不修改它们；不触发跨模块 `develop` 同步。
- 固定工作区 `E:\\Codex\\M2project`，分支 `m2`，远程 `https://github.com/FDU-Group16/Project1.git`。本地原为 `e307d29b1470ca5ec889c6c18a9096d4080cc479`，干净且为远端 `e1bae596679a9107905a96dde3a8008110acf1de` 的祖先。用户 2026-10-26 明确授权代理处理接入后，本地仅快进到该远端 SHA；没有合并提交或重放 B 文件。
- 快进后已重读根与 M2 局部规则、M2 状态、工程基线、内部协议、外部依赖和 B 进度。`origin/develop@99ce858a2bbf8caa2f4b226a83f989c54d6992d1` 已包含在当前 `m2` 历史中；本批不依赖新的跨模块能力。

## 目标与范围

- 需求：`M2-02`、`M2-03`、`X-02`、`E-01`、`E-07`。
- 目标：把 B 对已上传 A 共同值对象、拟议审批端口和资源回执恢复机制的评审转成可执行的 B1/B3 接口门槛。
- 本批仅可修改本文件、`services/m2/docs/progress/B.md`、`services/m2/STATUS.md`。不修改 A 的 `contracts.py`、`docs/contracts.md`、公开契约、数据库、迁移、业务路由、其他模块或前端。
- 不使用临时依赖。`contracts/m2.openapi.json@0.1.0-proposed` 和 `contracts/m1-room-blocks.openapi.json@0.1.0-proposed` 均未获批准；本批不改变版本或宣称业务端点可用。

## 方案与评审点

1. 对照 `services/m2/contracts.py` 及实际测试，确认 `Actor`、`TimeRange`、`ApplicationCreate` 是可导入的局部基础；`ApplicationView`、状态类型、Base/UoW、`ApplicationPort`、`ApprovalPort`、`ResourceCommandStore`、迁移链与正式装配仍未实现。B1 的 ORM 模型和端口实现继续等待同一基础，不复制定义。
2. `ApprovalPort.initialize` 拟接收 `ApplicationView`。A 建模时需明确该视图含申请 ID、可信申请人 ID/院系、已验证的审批路由和截止时间等初始化所需快照，并保证 A 创建申请、B 创建唯一一级待办和幂等结果在同一 UoW；B 端口不向 D 重新查询并自行选择审批路由。准确字段与签名由 A/B 在共同协议中评审后落实。
3. `ResourceCommandStore.save_result` 目前只返回布尔值，而协议正文要求在“回执已落盘、业务编排未结束”时崩溃后仍可恢复。A/B 在实现前须确定持久的未编排回执读取/领取入口，以及 B 完成申请状态、审批记录和原幂等操作时的同事务终结标记。可由 `claim` 返回该状态及回执，也可增加明确查询/终结方法；未确定前不能声称 B3 恢复路径可实现。
4. 资源恢复验收须模拟：M1 匹配成功、回执保存成功、进程在业务状态确认前终止；重启后只处理同一命令和原审批意图一次，过期或更高 RELEASED 不能被迟到 ACTIVE 覆盖。另测 `save_result=False` 的旧租约/替代回执不得推进申请。该测试需真实 A/B 存储与隔离 PostgreSQL；纯文档评审不构成通过。
5. 两级审批、截止公式、禁止自批与冲突清理仍按 `docs/decisions/0001-approval-expiry-policy.md` 的 Proposed 状态处理；以上接口门槛不批准这些业务政策。

## 验收与交接

- 核对新增 A 提交的 SHA、实际代码与文档状态，指出过时的“尚未上传”历史段落而不改 A 文件。
- 本批差异限于上述三个 B/M2 状态路径；新增本地链接目标存在，`git diff --check` 通过。
- `python -m unittest discover -s services/m2/tests -p 'test_*.py' -v` 首跑 25 项中 23 项通过、2 项环境错误：Windows 默认 GBK 无法解码 UTF-8 契约，以及运行时没有 `America/New_York` 时区数据。在本进程设置 `PYTHONUTF8=1`、`PYTHONTZPATH=C:\msys64\usr\share\zoneinfo` 后重跑 25/25 通过；未改依赖或测试。
- `bash scripts/check.sh` 在显式使用本任务隔离的 uv、同样的进程环境下通过：M1 OpenAPI 2 操作/引用、四服务本地 `/healthz`、Python 编译、Vue 类型检查与生产构建。该检查尚不运行 M2 单测或 M2 静态草案的专门校验。
- 无数据库或外部写调用。B1 待 Base/UoW/迁移/正式 Port；B3 待持久回执恢复入口及 A 命令仓储；M1/D 真实联调继续未验证。
- 评审人：B 技术自检；A 对共同签名与恢复入口需在后续共同基础批次评审。尚无队友批准、PR、迁移或部署证据。
