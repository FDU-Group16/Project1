# 临时测试账号

TEMPORARY-DEPENDENCY D-TEST-ACCOUNTS：仅用于用户授权的课程 staging/test 登录体验，不是 M2 提供的正式校园 D-01。契约与当前任务见 `contracts/test-accounts.md`、`services/d/tasks/2026-10-27-test-accounts.md`。本专用目录为临时实现的统一标记。

仅当 `D_TEST_ACCOUNTS_ENABLED=1` 且 `APP_ENV=staging` 或 `test` 才在 D 应用装配 context/login/me/logout/维修人员目录。默认关闭时所有这些临时路由均不存在；非法组合启动失败，绝不自动回退。正式身份负责人完成提供方后，按任务库存关闭并移除此目录、main 中装配、测试配置与标识；历史迁移/账号表不得随清理自动 DROP，M3/D-02 业务和真正 HTTP 消费代码必须保留。

## 初始化

先安全配置已有 PostgreSQL 的 `D_DATABASE_URL`，使用已拥有 `d` schema 的 D 账号。002 迁移只增加 `d.test_accounts`、`d.test_sessions`、`d.test_login_limits`，不访问其他服务表。应用与以下 CLI 都执行幂等迁移；种子与迁移分离。

```bash
APP_ENV=staging D_TEST_ACCOUNTS_ENABLED=1 \
python -m services.d.test_accounts.seed --output /private/path/test-accounts.txt --days 7
```

输出目录须预先存在，文件必须在源码 checkout 外，权限强制0600且属于执行用户；不覆盖已有文件。输出为 JSON，`accounts` 数组含 `username/password/expiresAt/user`，请通过私有渠道交付。CLI 日志只有新增/保留数量，没有密码、会话或数据库 URL。

默认生成四个独立随机密码；可传 `--credentials-stdin`，从标准输入读取精确四键的 JSON 映射：`m3-student`、`m3-admin`、`m3-worker1`、`m3-worker2`。每个密码20–128个可打印非空格ASCII字符，不能相同。不要将此 JSON 写入命令参数、仓库、公开日志或浏览器包。`validate_credentials(value)` 支持部署预检查，不输出敏感值。

重复执行不会重置密码、角色、停用标记或有效期，不会延长已到期账号；会核对已有私有文件并保持字节不变。若文件丢失，必须提供与已有账号匹配的显式密码才能重新交付；没有原密码则明确失败，不假称创建或自动重置。账号默认7天、允许1–30天。用户名固定，用户ID为 `test-` 加用户名，均无真实个人数据。

## 运行行为

密码以独立32字节盐的 PBKDF2-HMAC-SHA256（600000次，32字节摘要）保存。每次登录产生32字节随机 Bearer，数据库只保存SHA256摘要；有效期至多2小时且不超过账号到期。账号停用/到期、会话到期/撤销都立即失效；会话持久化，可跨进程重启校验。退出成功204。所有身份响应（包括错误）禁止缓存，带 `X-Identity-Mode: test-accounts`。

登录限速持久保存在PG：每个规范化用户名15分钟最多5次，全局15分钟最多100次，成功与失败均计数；覆盖未知用户名、跨worker与重启。使用短事务串行领取限额，密码计算在事务外。限速不依赖客户端 `X-Forwarded-*` 或宣称IP；不会因伪造代理头绕过。到期窗口自动清理。测试站在限额用尽后返回429，十五分钟后可重试。

公开context只返回测试模式，不列账号。响应user带`testAccount:true`；管理员仍按现有M3规则管理所有工单，未声明按测试房间隔离。维修人员目录仅维修管理员可读，只列未到期/未停用且有repair:work的账号。无注册、重置、真实用户管理或消息/审计服务。

## 验证

```bash
python -m unittest services.d.tests.test_test_accounts -v
```

guard测试不需要数据库；行为测试需要显式 `TEST_D_DATABASE_URL`，其数据库名必须含`test`。测试只清理上述三张测试账号表，不改D-02、M1或M3业务记录；不可对线上数据库运行。集成和公网部署证据由根任务记录，代码可用不等于线上账号已创建。
