# 临时测试账号接口

版本 0.1.0，proposed；仅课程 staging/test 显式启用，正式 D-01 仍待 M2 提供。兼容 `d-dependencies.md` 和 `m3-directory-dependencies.md` 的消费字段。

- `GET /api/v1/auth/context`：启用时 `{mode: "test-accounts"}`；关闭时不注册测试路由。此端点无需认证，不返回用户名、密码或密钥。
- `POST /api/v1/auth/login`：`{username, password}`；成功 `{accessToken, expiresAt, user}`。user 是 `{id, displayName, departmentId, permissions, testAccount: true}`。密码错误、未知或已过期账号统一 401；限速 429；不得回显密码。
- `GET /api/v1/auth/me`：有效 Bearer 返回同一 user；过期/撤销/伪造令牌或账号过期 401。
- `POST /api/v1/auth/logout`：撤销当前会话，成功 204；后续 me 401。
- `GET /api/v1/repair-technicians`：要求 repair:dispatch，返回 `{items: [...]}`，仅包含未过期且含 repair:work 的测试身份。其他有效用户 403。

响应禁止缓存。账号仅通过服务器命令创建，随机密码保存到权限 0600 的私有文件，数据库只存独立随机盐的 PBKDF2-HMAC-SHA256（600000 次）哈希。会话为至少 256 位随机值，库中只存摘要，最长两小时且不超过账号有效期。账号默认七天，最长三十天；退出立即撤销，重启可继续校验未到期会话。登录限速须覆盖已知及未知用户名，忽略客户端提供的代理身份头。

账号固定为报修人 `m3-student`（repair:report、seat:reserve）、管理员 `m3-admin`（repair:dispatch、repair:report）、维修员 `m3-worker1/2`（repair:work、repair:report）。均为合成测试身份，departmentId 为 null，不授予 room:manage 或 operations:read。管理员管理当前 M3 所有工单，沿用既有规则；不宣称资源范围隔离。

仅 `D_TEST_ACCOUNTS_ENABLED=1` 且 `APP_ENV=staging/test` 允许装配，非法组合启动失败；不得因真实身份故障自动开启。Web 使用已有密码表单，生产构建不启用公开开发 token 或身份选择器。
