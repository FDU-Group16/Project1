# 临时接口与可修改边界注释

## 范围与验收

- 用户要求优化此前检查出的临时接口注释，使其他负责组能在源码处看到临时用途、归属和可协调修改/替换范围。
- 关联 M1-01、M1-05、D-02、E-07/E-09；本次仅改注释、依赖清单及交接记录，不改运行逻辑、API 字段、契约版本、数据库或开发开关。
- 范围：M1 的 `dependencies.py`、`temporary_dependencies/`；D-02 的 `dependencies.py` 与 `development/`；Web `shared/auth/`、登录页/布局中的开发身份分支注释、`.env.example`，以及三方 STATUS。
- 维护/协作：M1 维护消费方临时适配；D-01 由 M2 负责，D-03/D-04 由 M3 负责；公共前端由 Web 维护者和 M1/D-02 消费组协调。具体个人评审尚未登记。
- 验收：临时实现及接入点具有统一 ID、提供方/消费方、可修改替换边界与清单引用；真实 HTTP 客户端仅标注契约假设可协调调整，不标成可整块删除；代码执行内容不变，根检查通过。

## 协作与同步

- 具体依赖是已确认的 D 子域分工和 Web 公共身份消费；采用现有 `origin`，在干净的 `.worktrees/m1` 工作区执行。
- 2026-10-27（Asia/Shanghai，本轮工具记录）：fetch 成功；`origin/develop=853708297ad7eea7be1570c0da233d9ee952cc57`，`origin/m1=0b37222251ae5cae07847ee3366fe33c3adadb66`。
- m1 从 `0b37222` 安全快进至 `8537082`，无未完成 Git 操作或需保留的未提交修改；已重读当前全局/Web 规则、模块索引、M1/D/Web 状态及 D 消费契约。
- 无新增 provider 能力；D-01/03/04 真实集成仍未验证。消费契约 `contracts/d-dependencies.md` v0.1.0 proposed 不因注释优化而获批准。

## 标注约定与现有临时依赖

- `TEMPORARY-DEPENDENCY <ID>`：可在对应集成任务范围内修改/替换的开发测试替身、接入分支或配置；提供方可用且联调通过后按清单清理。
- `CONTRACT-ASSUMPTION <ID>`：真实消费客户端当前采用的接口假设可由负责组协调修改；保留客户端、权限/错误处理、会话清理与消费者业务逻辑。
- 统一使用既有 ID：`M1-D-IDENTITY`（M2/D-01）、`M1-D-DELIVERY`（M3/D-03/D-04）、`D02-IDENTITY`（M2/D-01）、`WEB-D01-IDENTITY`（M2/D-01）。演示启动器统一引用这些 ID。
- 精确路径、配置、替换触发、检查和保留范围继续由 [M1 清单](../temporary_dependencies/README.md)、[D-02 清单](../../d/tasks/2026-10-22-d02.md#temporary-dependency-d02-identity)、[Web 清单](../../../apps/web/src/shared/auth/docs/auth-integration.md) 管理。本轮不新增替身、不自动执行替换或清理。

## 验证与交接

- 已补齐 M1 身份/投递、D-02 身份、Web 合成身份的文件头与接入点；真实客户端以 `CONTRACT-ASSUMPTION` 明确可协调接口映射，未被列为整块删除对象。
- 演示启动器使用四个清单中的统一 ID，移除原先不一致的 `M1-D01/M1-D03/M1-D04` 别名；模块文档字符串同步更新 CLI 帮助说明，启动流程不变。
- 5 个 Python 源文件去除注释/文档字符串后的 AST 与基线一致；6 个 Web 代码/配置文件去注释后与编辑前逐字一致，Vue 模板与样式完全一致；Web 类型检查通过。
- `bash scripts/check.sh` 在实际 m1 工作区通过：26 项 OpenAPI 操作及引用、四服务 HTTP 健康检查、隔离 PostgreSQL 的 D 14 项与 M1 30 项测试、真实 D-02→M1 HTTP/账号隔离/停止提供方失败、两项关键行为变异检查、Vue 类型和生产构建。
- `git diff --check`、修改文档的本地链接目标检查通过；临时标记与清单统一，未引入新的临时依赖或迁移。
- 本轮未重新验证浏览器业务或真实 D-01/03/04；代码注释不是提供方已实现、真实联调或部署通过的证据。
- 按本次会话已授权流程将注释提交合入 m1/develop 并普通推送，提交号由包含本记录的 Git 历史确定，远端结果以引用核对为准；更新 M1、D 和 Web 公共 STATUS，原临时依赖库存继续有效。
