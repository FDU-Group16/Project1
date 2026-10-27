# 公网测试账号任务

用户明确要求在 `pj1.756888.xyz` 登录体验 M3，复用 develop 自带 PostgreSQL，不另建数据库服务。范围是临时测试账号，不交付完整校园 D-01，也不修改 M1/M2 业务。

## 同步与范围

2026-10-27：`工程伦理/develop/Project1` 的 `m3-develop` 起点为 `7012905`，工作区干净；通过 origin 获取 develop，按根规则安全快进至 `91ff58cc9166ab88aec301b043b9b00f72d377fa`（PR #3 合并）。已阅读根、Web、M3 规则，D/M3 状态及身份契约。新基线仍无 D-01 登录提供方。修改范围限定 D 的临时账号适配、独立迁移/种子、Web 测试身份标识、staging 配置与初始化脚本、必要测试和交接；M3 集成，D-01/M2、D-02/M1、公共 Web 及部署负责人合入前评审。

## 验收

- 四个合成账号：报修人、维修管理员、两位维修员，支持登录/刷新/退出及按权限显示 M3 功能，后端继续验证全部权限。
- 正常生产默认关闭；仅显式 staging/test 开启。账号有限期、随机独立密码、加盐哈希；会话随机且可过期/撤销；错误密码不登录，有限速。不把密码、令牌写入 Git、日志或浏览器包。
- 复用已有 PostgreSQL 的 d schema 存账号及会话，不读写 M1/M3 数据；迁移与幂等种子分开。已有业务数据、数据库密码和配置不得被覆盖。
- 服务器初始化仅补缺少的角色/配置，提供一次执行入口。密码仅在服务器私有文件交付。真实上线需服务器操作与实际 HTTP 登录验证，代码测试不等于线上生效。
- 不变更现有权限规则，不声称测试管理员仅能管理某一测试房间；应在课程测试站使用。真实 D-01、通知和公共审计仍未交付。

## 临时依赖库存

`D-TEST-ACCOUNTS`：M3/Web/D-02 消费 M2 所属 D-01。契约见 `contracts/test-accounts.md@0.1.0`（proposed）。实现独立置于 `services/d/test_accounts/`；仅 `D_TEST_ACCOUNTS_ENABLED=1` 且 `APP_ENV=staging/test` 装配。Web 根据运行时 context/identity 的测试标识展示提示；默认登录客户端及生产构建不伪造用户。

提供方正式就绪后，由 M2、消费方和部署负责人核对 login/me/logout/维修人员目录接口，关闭开关，完成真实登录/撤销/权限及全流程测试，再移除临时路由/种子/测试标识配置。保留 M3 业务、HTTP 客户端、权限检查、真实提供方验证测试；临时表不可随代码清理自动 DROP。D-01 PROVIDES 保持 not_ready，临时密码验证不冒充正式校园身份接入。

## 交付状态

已实现临时密码账号、迁移、私有幂等种子、公共 Web 提示和既有 staging 流水线的可选初始化。精确配置见 [部署说明](../../../docs/deployment-test-accounts.md)。新 Secret 非空才走已有 SSH 通道，JSON只经stdin传输；本轮未连接服务器、未更改线上配置、未上传或部署。

本机验证（2026-10-27，`91ff58c` 上本轮工作树）：

- `BUSINESS_TEST_EXTERNAL=1 bash scripts/check.sh` 全通过，使用专用 PostgreSQL **16.2**：D 26项（原14 + 账号12）、M1 30项、M3 PostgreSQL83及SQLite83、依赖登记24、部署测试账号边界7；M1两项/M3三项定向变异仍被捕获，前端类型和生产构建通过。
- 真实临时密码账号→D/M1/M3 HTTP链路通过：四角色权限、私有幂等种子、密码/会话摘要、错误密码拒绝、服务重启后恢复、跨角色禁止、完整报修/派单/维修/验收/评价、退出撤销、未知用户名限速和伪造代理头无效。使用真实临时密码服务，无忽略密码的身份fixture。
- `services/m3/tests/browser_test_accounts.py` 通过：Chrome中四账号密码登录、刷新/me、退出撤销、重派及全流程、可选context 404兼容、M2入口、320px布局和共享请求客户端回归；桌面和手机截图已检查。验收随机密码文件及启动进程结束后清理。
- 原 `scripts/test-staging-images.py` 9项通过。原有真实M3→M1→D-02隔离/多来源验收继续通过；其历史身份fixture证据与本轮临时密码服务证据分开记录。
- 本机无 Docker；本轮 PostgreSQL18、容器实际运行、GitHub CI、服务器初始化与公网账号均 **未验证/未执行**，不沿用上次PR #3的绿色状态声称本次通过。

本机证据：`工程伦理/.verification/test-accounts-check.log`、`工程伦理/.verification/test-accounts-browser-20261027T082112Z-43eb9a/summary.json` 和截图目录。手机截图等待渲染稳定后重新验收，DOM唯一性和上下视口/全页截图一致，页面无重复布局。Nginx在API配置更新后单独重建以刷新服务IP，7项部署边界检查再次通过。不包含真实个人信息或线上密码。用户实际待上线的四组密码只在仓库外 `工程伦理/测试账号/` 私有文件中，不是验收夹具。

临时部署入口也在清理库存：`scripts/bootstrap-test-accounts.py`、`enable-staging-test-accounts.sh`、`enable-staging-test-accounts-remote.sh`、`verify-staging-test-accounts.py`；Compose 的 `D_APP_ENV/D_TEST_ACCOUNTS_ENABLED`，工作流的 `STAGING_TEST_ACCOUNTS_JSON`。Web临时显示字段登记到既有WEB-D01-IDENTITY库存。提供方正式就绪后先关闭并验收，再按清单移除；保留已有数据、服务令牌、数据库隔离和业务权限。
