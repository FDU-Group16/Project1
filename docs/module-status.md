# 模块状态与 Agent 交接入口

本文件只维护入口，具体完成内容由各模块自己的 `STATUS.md` 记录。Agent 先读取任务涉及的本模块状态；需要其他业务模块或 D 等公共部分协作时，再按 [全局规则](../AGENTS.md)尝试同步 develop，并确认相关提供方的状态及契约。单模块独立任务不强制同步。接口提案、代码实现、测试通过、合并到集成分支与远端部署是不同事实，必须分别核对。

## 模块记录

| 范围 | 交接记录 | 用途 |
| --- | --- | --- |
| M1 后端 | [services/m1/STATUS.md](../services/m1/STATUS.md) | 预约、签到、可约状态及 M2/M3 写回接口的实际实现与验证 |
| M2 后端 | [services/m2/STATUS.md](../services/m2/STATUS.md) | 整室申请、审批及对 M1/D 的依赖 |
| M3 后端 | [services/m3/STATUS.md](../services/m3/STATUS.md) | 工单、维修、验收及对 M1/D 的依赖 |
| D 后端 | [services/d/STATUS.md](../services/d/STATUS.md) | 身份、权限、主数据、通知、审计与责任决策 |
| Web 公共部分 | [apps/web/STATUS.md](../apps/web/STATUS.md) | 布局、公共组件、路由汇总和公共基础设施 |
| M1 前端 | [modules/m1/STATUS.md](../apps/web/src/modules/m1/STATUS.md) | M1 页面、路由及与 M1 后端的接入情况 |
| M2 前端 | [modules/m2/STATUS.md](../apps/web/src/modules/m2/STATUS.md) | M2 页面、路由及与 M2 后端的接入情况 |
| M3 前端 | [modules/m3/STATUS.md](../apps/web/src/modules/m3/STATUS.md) | M3 页面、路由及与 M3 后端的接入情况 |

## 接口与需求的权威入口

- [接口契约登记](../contracts/README.md)：查看契约状态、版本与兼容性；接口字段、鉴权、错误和示例写在相应契约中。
- [需求与验收基线](requirements.md)：查看需求 ID、验收条件及实现/验证追溯；需求“已明确”不等于“已实现”。
- [架构决策](decisions/0001-stack.md)与 [D 归属提案](decisions/0002-d-ownership.md)：确认决定是否获批，不能将 `proposed` 当作团队共识。
- [AI 任务模板](ai-task-template.md)：在开始任务时列出依赖，完成时逐项填写交接。

例如 M2 要接入座位占用写回，应尝试同步 develop，阅读 M2 自身记录、M1 提供方记录和房间阻断契约；涉及身份与房间 ID 时再读 D 的记录。若 M1 只有契约提案，应在 M2 的交接中说明缺口，不代写 M1；若需要补充公共 D 能力，可在明确任务范围、验收和评审要求后实施。获取远程失败时，注明远程最新情况未确认。

## 更新方式

每个模块的 `STATUS.md` 保持“当前状态、可用入口、验证与发布证据、依赖与待办、最近交接”几个部分。任务完成时和代码一起更新，链接到具体任务说明与源码；跨模块接口变更更新共享契约，并在本模块任务/交接中列出消费方影响，由各业务模块在各自任务中更新记录和实现。正常进度更新不修改本索引，新增模块或入口变化时再调整链接。

记录仅对写明的工作区、提交或环境成立。相同检出目录下的 Agent 可立即读取；不同分支、工作树或电脑要通过提交与 PR 同步，不能自动看到彼此未提交的进度。人工验收、发布 tag、迁移版本与远端运行结果只在有证据后记录。
