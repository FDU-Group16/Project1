# M1 合入 develop 与本地启动工具协调

## 目标、授权与范围

- 2026-10-27 用户明确要求协调 develop 中已有五项未提交改动，将 m1 提交合入 develop 并推送远程；该授权包含已说明的 README/Web 状态冲突协调。
- 需求：M1-01～08、D-02 的已有实现集成；E-01/E-07/E-08 的公共本地启动支撑。
- 共享依赖：M1 与 D-02 的现有 ASGI/HTTP 入口、公共 Web/Vite 及启动环境。
- 允许 authored 修改：`scripts/dev.py`、根 README、`docs/requirements.md` 的 E-08 证据、原本地启动任务、本记录，以及 M1/D-02 前后端与 Web 公共 STATUS 的集成交接。用户随后补充确认 D 任务分工已定，允许同步上述分工相关共享文档及当前消费方依赖库存；不改 M2/M3 的私有记录。M2/M3、业务规则、契约和 schema 不作新增修改。
- 验收：M1 所有提交可从 develop 到达；原五项工作经协调保留；通用启动器真实启动/退出与端口冲突检查通过，默认不启用替身；根 `bash scripts/check.sh` 通过；远程 develop 与本地提交一致。
- 集成执行由本任务负责；后续业务/契约审查责任仍为 M1/D-02/Web 公共维护组及相关提供方，未指定或虚构个人评审结果。

## 分支与改动保全

- 工作区：仓库根目录，分支 `develop`；初始 HEAD `c539d18b4fde2ec80fab9fc1fedd89230c01da04`。
- 原有未提交改动：README、Web STATUS、requirements，以及新增 `scripts/dev.py`、`docs/tasks/2026-10-22-local-dev.md`；原始内容完整保存于命名 stash `pre-m1-integration-2026-10-27 local launcher and docs`，对象 `df9e3ca4aecb5fc495c363591d08c282ba9a3222`，另有仓库外临时文件备份。无进行中的 merge/rebase 或未解决索引冲突。
- 2026-10-27 13:33（Asia/Shanghai）整理同步证据：本轮通过现有 origin（`https://github.com/FDU-Group16/Project1.git`）fetch develop/m1 成功；`origin/develop` 与 `origin/m1` 均为 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`。
- 来源 `m1=0b37222251ae5cae07847ee3366fe33c3adadb66`，比远程 develop 多 19 个业务提交；本地 develop 初始另落后已发布的 2 个静态界面提交。所有历史可快进，无分支历史冲突。
- 已执行 `git merge --ff-only m1`，本地 develop 变为上述 m1 SHA。重新读取当前全局/Web 规则、模块索引、M1/D-02 前后端和 Web STATUS、契约登记；在实际检出上验证。
- 原有 stash 已恢复：requirements 自动合入；README 和 Web STATUS 按下节协调；两个新增文件保留。stash 继续作为原始备份，不再次整体 apply，以免重复恢复旧说明。

## 协调结果

- README 保留 M1/D-02 的真实业务范围、显式合成业务演示入口和依赖缺口，恢复通用一键启动、安装/重载/地址/清理说明，去掉当前“仅有健康端点”“代理未接入”的过时断言。
- 通用 `scripts/dev.py` 自检增加 psycopg，并显示 M1/D 健康响应中的实际依赖模式。保留四 API + Vite、依赖准备、热重载、日志和进程回收；继承终端环境，不自行配置数据库、凭据、身份或调度器。
- `run_demo` 的数据库、合成身份与调度器启动行为保留在现有显式命令中，本次未扩展或复制业务替身。临时依赖库存继续以 [M1](../../services/m1/temporary_dependencies/README.md)、[D-02](../../services/d/tasks/2026-10-22-d02.md#temporary-dependency-d02-identity)、[Web](../../apps/web/src/shared/auth/docs/auth-integration.md) 为准；本次未新增临时依赖、未执行替换清理。
- E-08 原有启动器证据链接保留；原任务的 2026-10-22 骨架测试标注为历史，增加本次适配说明；各 affected STATUS 更新集成范围，保留已有未完成项。
- 契约版本不变：M1 公共 v0.1.0-proposed、D-02 v0.1.0 proposed、M1 写回 v0.2.0-proposed；本次无迁移新增。接口契约的 proposed 状态保持不变。用户在本轮另行明确 D 的任务划分已经确定，因此按现有表格登记 M1→D-02、M2→D-01、M3→D-03/D-04；ADR、全局规则、需求/计划/架构、伦理记录和相关当前说明同步修正。公共前端治理、具体评审及发布轮值不由这条分工确认一并批准。

## 验证与交付

- `bash scripts/check.sh` 在本次根工作区 `develop@0b37222` 加协调改动上通过：26 项 OpenAPI 操作/本地引用、四服务 HTTP 健康检查、新建隔离 PostgreSQL 的 D 14 项 / M1 30 项测试、真实 M1→D-02 HTTP/账号 schema 隔离/依赖停止 503、两项关键行为变异检查、Vue 类型及生产构建。测试容器由脚本清理。
- 通用启动器的 `--help` 与 AST 语法检查通过；使用仓库外临时验证脚本，从 `/private/tmp` 调用真实启动器，分别运行默认热重载与 `--no-reload`。五个 HTTP 入口可访问；默认 M1 模式 `real`、D 模式 `real-http`；无身份配置时持合成字符串的业务请求返回 503，无替身回退。SIGTERM/SIGINT 后五端口与本次子进程清理通过；预占 3101 时启动器报错且已有监听保留。
- 本轮不重复执行历史完整浏览器回归，不验证全新机器安装或无 uv 的 pip 首装；现有锁文件依赖已由根检查同步。
- `git diff HEAD --check`、受影响 Markdown 本地文件链接检查通过；README/Web STATUS 的冲突已按双方意图协调，提交时统一标记解决。原始 stash 仍保留备查。
- 交付目标为 `origin/develop` 的普通快进推送，包含已有 m1 提交与本次协调提交；不 force-push、不修改 main。协调提交号以包含本记录的 Git 历史为准；远端接收通过 `git ls-remote origin refs/heads/develop` 核对，CI/部署以该提交对应的 GitHub Actions 记录为准。

已知 D-01/03/04 真实提供方、M2/M3 实际业务写回仍未集成；既有浏览器业务证据来自 2026-10-22，本次不重复宣称新的浏览器业务验收。

推送 develop 会触发现有 CI 和 Staging deployment 工作流。本次不改发布配置；工作流状态与真实业务部署可用性分别记录，健康检查不替代数据库/身份/调度器联调。生产发布、release tag 和远端业务迁移均未验证。

M2/M3 自有 STATUS 中仍可能保留 2026-10-22 的 D 归属或提供方未实现描述，属于旧交接证据；其负责组后续同步。当前归属以已更新 ADR 为准，提供方能力以当前代码、契约和实际联调为准，本次不代改其模块记录。
