# M3 适配 develop 的独立交付副本

2026-10-27，用户明确要求将现有 M3 整合适配 develop，可新建子目录方便上传。本目录为 `工程伦理/develop/Project1`，从实际 fetch 的 `origin/develop@13dcd59f9a46c859f8593b530d7aa54c27faaf1f` 建立 `m3-develop`；原 `工程伦理/Project1` 的 M3 工作区和分支保留，不执行合并冲突选边、覆盖原工作区或直接推送 develop。

## 范围与评审责任

- M3 前后端：迁入现有工单实现，并适配最新 D-02、M1 写回 `0.2.0-proposed`、公共身份状态和 HTTP 入口。
- 共享范围：依赖/锁文件、M3 代理、公共请求的取消与错误兼容、显式开发身份的维修角色、三模块独立数据库账号/迁移启动、保留既有检查的测试/CI、依赖登记、相应状态和需求追溯。保留 develop 的现有 M1/D-02 业务和全部验收，不改其业务代码。
- 本次由 M3 集成；M1/D-02 负责人评审真实写回、主数据和凭据，M2/D-01 与公共 Web 负责人评审身份消费提案，数据库/部署维护者评审角色、迁移与 CI。Agent 检查不表示已获人工批准。
- D-03/D-04 归 M3 组，但本次任务为已完成工单的适配，没有新增公共通知或审计子域；其提供状态保持 `not_ready`。工单历史不等于公共审计服务。

## 契约适配决策

外部及 M3 后端路径继续使用 `/api/m3/v1`；共享 `request('m3','/v1/...')` 生成该地址。M1/D 现有前缀剥离与路径保持原样。M3 使用共享登录会话，不建立第二套前端登录。

D-01 提供方仍未实现。本次仅增加明确的消费方提案：可信 `/api/v1/auth/me` 返回 `id/displayName/departmentId/permissions`；`repair:dispatch`、`repair:work`、`repair:report` 分别授予维修管理员、维修员、报修人，优先级 dispatch > work > report，已有 `seat:reserve` 可作为报修资格。`room:manage`/`operations:read` 不自动授予维修管理权限。管理员读取拟议 `GET /api/v1/repair-technicians` 的 `items:[{id,displayName,permissions}]`，每项必须含 `repair:work`。具体规范同步至 contracts，未将提案当作可用 D-01 服务。

M3 真实目录适配逐请求校验用户身份，并以用户 Bearer 调用 D-02 的公开房间接口，保留院系/可见范围过滤；不借用 M1 专用内部服务令牌。正常运行使用显式 HTTP 配置，外部失败返回真实错误，禁止开发回退。仅测试/本地演示可启用合成身份。

## 验收

1. 保留原 M3 状态、权限、SLA、幂等、版本、租约/重试及持久化行为。
2. 新真实 HTTP 目录适配覆盖身份失效、权限不足、房间范围、人员目录错误和依赖不可用；正常模式不要求缺失提供方假成功。
3. 使用真实 M3/M1/D-02 应用和独立 PostgreSQL schema，通过网络验证全室下架、待验收保留、单来源释放、双工单/M2/个人预约限制保留。D-01 可由明确的测试 HTTP 服务替代，证据单列。
4. 根检查保留 develop 的依赖登记、M1/D 业务与变异测试，同时加入 M3 与真实联调门禁；前端类型/构建和共享登录下真实浏览器回归。
5. 提供独立源码目录、差异补丁/变更清单与上传说明；没有推送/PR/部署或人工评审时明确标注。

## 本地验证结果（2026-10-27）

- `BUSINESS_TEST_EXTERNAL=1 bash scripts/check.sh`：通过。使用专用 PostgreSQL **16.2** 测试库及 M1/D/M3 三个 schema owner；M3 PostgreSQL **83 passed**，同一检查再运行 SQLite **83 passed**。
- 保留的 develop 回归：D-02 **14**、M1 **30**、依赖登记行为 **24** 项通过；M1→D-02 真实 HTTP 集成通过；M1 两项变异与 M3 三项变异均被测试捕获。
- 新真实 M3→M1→D-02 HTTP 集成通过：房间范围、整室下架、待验收保持、两张 M3 工单、M2 和个人预约保留、迟到旧 ACTIVE 墓碑拒绝、六项跨 schema 权限拒绝及依赖停机。D-01 是明确的 HTTP 测试身份服务，M1 身份/通知/审计仍为显式开发替身。
- 实测发现并修复已有 schema 的迁移权限问题：PostgreSQL 的 `CREATE SCHEMA IF NOT EXISTS` 仍要求数据库 CREATE 权限；现在先检查 schema 是否存在，再在缺失时创建。既有独立 schema owner 可正常迁移，不扩大其权限；专门回归验证无数据库 CREATE 权限。
- `scripts/test-staging-images.py` **9** 项通过；shell 语法检查通过；根检查中的 Vue 类型与生产构建通过。
- 本机没有 Docker，**PostgreSQL 18、Docker 镜像/Compose运行、远程 CI 尚未执行**。默认 `scripts/test-business.py` 与 CI 仍使用 `postgres:18-alpine`，失败阻断后续交付。16.2 实测不能代替 18 的合入门禁。
- `services/m3/tests/browser_real_providers.py --port 5174`：通过。真实 Chrome + M3/M1/D-02/PostgreSQL，显式合成共享身份。覆盖统一登录/切换/退出、完整报修/派单/维修/返工/代验/评价、回执后关闭、越权隔离、M1/D 实际业务及 M2 页面、1440/768/375/320 布局和键盘焦点；页面 JavaScript 错误 0。桌面/手机截图人工查看无内容溢出。
- 共享 HTTP 客户端六组浏览器回归通过：M1 Problem+JSON、M3 嵌套错误、当前会话401清理、调用方取消、旧200/401响应拒绝且保留新身份、M2刷新。仅此客户端传输测试拦截专用 `__transport-test` 地址，未替换业务端点。
- 没有推送/PR/合并/部署或人工评审通过记录。

## 部署前必须补齐

1. M2/D-01 实现统一登录/me/logout 与本次拟议维修权限、人员目录，并完成受影响组契约评审。单独设置 `D_IDENTITY_URL` 不能令前端 `/api/d/api/v1/auth/*` 或 M1 身份接口凭空出现；需要真实 D-01 路由提供方。
2. 管理员通过 `scripts/provision-databases.py` 配置 M1/D/M3 独立账号和 schema，设置三个 DATABASE_URL、D_M1_TOKEN、M3_M1_TOKEN、独立 M1_M2_TOKEN 与 M1_CHECKIN_SECRET。仅把现有应用换成新镜像而不配置业务数据库，健康检查仍可能通过，业务不会可用。
3. 共享配置、数据库和接口经相关负责人评审，PG18 CI 通过后再 PR 合入 develop；若基线有新变化，由负责人核对差异，不整体覆盖或自动选边解决冲突。
4. 合入触发既有测试站部署后，核对发布提交、迁移版本、统一登录与实际工单业务；本次新增 context 探测只检查 M3 同域路由可达，不是业务集成验收。D-03/D-04 仍另行实施。

## 可交付目录

`工程伦理/develop/Project1` 为完整独立 Git 工作区，工作分支 `m3-develop`；源目录未更改。旁边提供上传说明、包含新增文件的差异补丁与可移交源码压缩包。工作区本次变更未提交；使用补丁时须先核对基线并 `git apply --check`，不把旧目录直接覆盖最新 develop。
