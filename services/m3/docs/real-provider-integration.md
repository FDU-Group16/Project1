# 最新 develop 的 M3 真实提供方验收

工作区：`工程伦理/develop/Project1`；基线 `origin/develop@13dcd59f9a46c859f8593b530d7aa54c27faaf1f`。原独立重建目录保持不变。M1 写回契约为 `0.2.0-proposed`，D-02 为 `0.1.0-proposed`；提供实现存在仍不等于相关负责人批准契约。

## 测试范围与边界

`../tests/integration_real_providers.py` 启动真实 M3、M1、D-02 三个 HTTP 进程并使用真实 PostgreSQL，各服务凭据仅可访问自己的 schema；工单操作经 M3 公共 HTTP API 驱动，实际 worker 网络调用 M1，M1 经网络读取 D-02。验收断言通过公共 API 与权限只读探针获得，不直接修改其他服务表，也不替换业务函数。

D-01 仍未实现：M3 与 D-02 通过真实身份 HTTP 适配器调用独立的合成身份 fixture。M1 保留明确开发身份/投递模式，但主数据始终调用真实 D-02。测试不证明真实账号认证、会话失效、D 通知或审计送达，也不代表部署验收。

## 场景

- D-02 创建三座位公共房间及另院系房间，M3 真实目录过滤不可见房间，直接越权报修被拒绝。
- 时段 A 保留一张个人预约，时段 B 建立 M2 占用；两张 M3 工单依次启动，实际整室下架，包括尚无预约的座位。
- 完工待验收持续下架；第一张工单验收后仍被第二来源阻断；两张均关闭后，A 仅原预约座位不可用，B 仍由 M2 阻断。释放 M2 后 B 全部恢复。
- 真实 M1 追溯中存在 M1/M2/M3；每张 M3 工单 ACTIVE revision 1、RELEASED revision 2 独立保存，迟到旧 ACTIVE 返回 409 且不重新阻断。
- 三组数据库角色的六个跨 schema 读请求均必须被数据库权限拒绝。
- D-02 停止后真实目录与 M1 搜索返回 503；新维修写回保留 BLOCK_PENDING、等待重试，不能假成功。

座位恢复检查使用没有个人预约的第二名学生，因为 M1 会对已有重叠预约的查询者隐藏所有候选座位，不能把该规则误判为维修仍阻断。

## 运行与证据

先按根测试启动器建立一次性数据库及 M1/D/M3 三个角色/schema，然后顺序运行；必填 `TEST_M1_DATABASE_URL`、`TEST_D_DATABASE_URL`、`TEST_M3_DATABASE_URL` 及明确清理授权 `M3_TEST_ALLOW_RESET=1`，禁止与其他清表测试进程并行。脚本运行前后仅清空 M3 自有 outbox/幂等/工单数据，保留 schema、迁移版本与事务 guard；绝不清空 M1/D 表。测试自己创建的个人预约在结束时经 M1 取消 API 释放。其余集成数据保留在一次性库内，由根启动器统一销毁。

场景预约使用明日 06:00 UTC，避开既有 M1/D 集成脚本的 02:00 UTC 时段，防止同一合成学生在其他场景已有预约而造成误判。脚本随机生成服务令牌，退出时停止自己启动的 HTTP 子进程，不输出凭据。

浏览器辅助身份进程可运行：`python services/m3/tests/integration_real_providers.py --identity-fixture --port 3115`。仅监听回环地址，返回 `X-Identity-Fixture: synthetic-test-only`；合成用户键见脚本 `IDENTITIES`，不是生产账号。供本地交互使用的登录便利接口不实现真实密码验证，禁止部署。

完整浏览器复验运行器：`.venv/bin/python services/m3/tests/browser_real_providers.py`。同样需要三个专用 `TEST_*_DATABASE_URL` 与 `M3_TEST_ALLOW_RESET=1`；外部 Playwright 工具通过 `NODE_PATH` 提供。运行器动态选择回环端口（可用 `--port 5174` 固定 Vite），以真实 M3 production/http、真实 M1、真实 D-02 启动，公共登录显式启用合成开发身份；通过 D API 创建自己的公共房间后传入 `M3_TEST_ROOM_ID`，依次运行 M3 完整流程、既有 M1/D 浏览器业务回归和公共客户端传输回归。M3 脚本同时检验 M1/M2 路由、窄屏与退出后隔离。结束时停止自己的进程并清理 M3 测试数据，不杀其他端口上的进程。

## 实际执行结果（2026-10-27）

- 根任务在本机隔离 PostgreSQL **16.2**、三个独立 schema owner 下执行 `bash scripts/check.sh`（`BUSINESS_TEST_EXTERNAL=1`），完整退出码为 **0**。本脚本输出 `PASS real M3 -> M1 -> D-02 HTTP/PostgreSQL`：上述整室下架、待验收保留、两个真实 M3 来源、M2/个人预约保留、旧版本墓碑、六项跨 schema 拒绝与真实 D-02 停机行为均通过。
- 同轮 M3 PostgreSQL **83 passed**、SQLite **83 passed**；既有 M1 **30 项**、D **14 项**及真实 M1/D HTTP 链路通过，依赖检查 **24 项**通过，M1 两项和 M3 三项定向变异均被对应测试发现。根检查还通过 Vue 类型与构建；部署镜像行为测试另外执行 **9 项通过**。
- 首次真实三角色启动暴露 Alembic 环境的权限问题：`CREATE SCHEMA IF NOT EXISTS m3` 即使目标已存在也要求数据库级 CREATE 权限。修复为先查询 schema 是否存在、仅缺失时请求创建；没有扩大服务角色权限。修复后重新完整执行通过，六项跨 schema 拒绝断言仍通过。
- 完整执行日志位于本任务上层 `.verification/develop-check.log`，属于本机证据，不纳入源码或作为远端 CI 记录。启动失败诊断先脱敏全部已知 DSN/密码/token/secret，并遮盖数据库 URL 与带凭据 HTTP URL 后才输出日志末尾；合成敏感值的脱敏检查已通过。
- 完整真实提供方浏览器运行器执行退出码为 **0**，三个脚本全部通过：M3 报修/派单/维修/返工/管理员代验/回执关闭/一次评价/刷新/身份切换与退出；既有 M1 搜索/预约/取消/再次预约和 D-02 房间座位管理/注销；公共客户端 401 清理、取消请求、切身份后的迟到响应隔离及 M1/M3 错误格式。M3 使用 production/http 装配，公共登录明确展示合成开发身份；M1/M2 路由回归通过，JavaScript 错误 **0**。
- 浏览器覆盖 1440/768/375/320px 宽度；桌面与手机截图由根任务实际查看，无横向溢出。日志位于本任务上层 `.verification/develop-browser.log`；仓库摘要证据见 [verification-results.txt](verification-results.txt)。这是本轮真实 M1/D-02/M3 与 PostgreSQL 的结果，不采用旧目录 M1 HTTP 替身结果替代。
- PostgreSQL **18** 仅在 CI/Docker 配置中，本机缺 Docker，未执行该版本；远端推送、CI、部署与真实 D-01 均未验证。
