# 公共身份消费与临时依赖记录

更新：2026-10-27。原实现与验收记录来自 2026-10-22；本次补充临时接口注释及可修改范围，不改变运行行为，不表示真实 D-01 已联调或部署。

## 范围与验收

本轮 M1-01～M1-08 与 D-02 页面需要同一个身份状态、公共 HTTP 错误处理、路由保护和公开 API 代理。仅实现 D-01 的 Web 消费接口；不创建真实账号、角色提供方、通知中心或审计服务。父任务负责集成，M1/D-02 与 Web 公共维护组负责合并前评审，D-01 所属组负责身份契约评审。

验收：默认使用真实身份 HTTP；失败不能成为模拟登录；跨用户切换、登出和 401 清除页面状态；安全的站内返回路径；只暴露公开 `/api/v1/`，不转发 `/internal/`；原 M2/M3 介绍页和只读示例保持可达。契约：[D 依赖提案 v0.1.0](../../../../../../contracts/d-dependencies.md)，仍待提供方评审。

## 实现

- `session.ts` 只在 sessionStorage 保存当前会话，按服务端 expiresAt 过期；不保存密码。刷新通过 `/auth/me` 验证恢复，故障时清理凭据并提示重登。
- `index.ts` 调用真实 D `/api/v1/auth/login`（username/password）、`/me`、`/logout`。退出时始终清理本地状态，服务端撤销失败会显示说明。
- `shared/api/client.ts` 统一 Bearer、15 秒超时、Problem 错误和 401；每个响应核对请求开始时的身份版本，旧身份响应被拒绝。`App.vue` 按身份版本和路由路径重建页面，防止旧页面请求重新写入新身份视图。
- 路由守卫只提供显示保护；院系和业务权限由真实后端校验。`redirect` 只允许已注册站内路径，排除协议相对、反斜线、控制字符及登录循环。
- 开发 Vite 代理使用 `M1_PROXY_TARGET` / `D_PROXY_TARGET`；默认本机 3101 / 3104。Nginx 使用 Compose 服务的对应内部端口。仅 `/api/m1/api/v1/*`、`/api/d/api/v1/*` 转发，内部凭据不进入浏览器。

## TEMPORARY-DEPENDENCY WEB-D01-IDENTITY

2026-10-27：本清单已接入 [DEPENDENCIES.json](../DEPENDENCIES.json)。M2 可按 D-01 查询此 Web 接入缺口；Web/M1 在真实验证、清理后更新消费记录，步骤见[交接指南](../../../../../../docs/temporary-dependency-handoff.md)。本次仅补充登记，真实 D-01 仍未联调。

| 项 | 记录 |
| --- | --- |
| 消费方/提供方 | Web M1/D-02 → D-01（M2 组）；真实提供方仍未集成 |
| 精确临时路径 | `apps/web/src/shared/auth/dev-identities.ts`；`index.ts` 中开发选择、合成恢复和退出旁路；`session.ts` 的本地 `synthetic` 标记；`LoginPage.vue` 开发选择表单及其状态/处理函数；`AppLayout.vue` 开发横幅及专用样式；`apps/web/.env.example` 中开发开关及说明 |
| 启用 | 仅 Vite development 且显式 `VITE_USE_DEV_IDENTITY=true`；后端仍须分别启用其开发身份配置。生产构建即使设置此变量也不启用 |
| 合成输入 | cs/ee 学生、空间管理员、运营四种固定身份，固定非秘密开发令牌。无密码验证、不声称真实身份 |
| 限制 | 不模拟主数据/预约结果；所有业务请求仍由真实 HTTP 服务处理。请求失败没有替身回退 |
| 拥有/集成组 | Web 公共维护组、M1/D-02 消费组与 M2/D-01 提供组协调；此处不扩大为全部公共前端的归属决定 |
| 替换触发 | 真实 D-01 提供方可用，契约及测试账号确认，明确授权替换路径 |
| 必需验证 | 真实登录/恢复/过期/退出、不同院系、401/403、角色切换、并发旧请求、代理边界；然后运行 `bash scripts/check.sh` |
| 删除范围 | 临时身份文件及以上分支/提示、相关开发启动配置；按集成任务范围删除，不自动清理其他组 |
| 保留代码 | HTTP、真实身份客户端、会话清理、路由守卫、业务页面、API 适配、正常错误处理 |

## 可直接定位的修改边界

- `TEMPORARY-DEPENDENCY WEB-D01-IDENTITY` 标注上表的开发替身及接入点。M2/D-01 提供组与 Web/M1/D-02 消费组可在明确的集成任务范围内修改或替换这些临时内容；真实联调通过后按清单清理，不删除真实客户端、会话清理或消费方业务。
- `CONTRACT-ASSUMPTION WEB-D01-IDENTITY` 标注 `index.ts` 的 `restoreIdentity`、`login`、`logout` 真实 HTTP 消费接口，以及 `session.ts` 的 `Identity`/`Session` 字段假设。它们采用 [D 依赖提案 v0.1.0](../../../../../../contracts/d-dependencies.md)，可与 M2 协调路径、字段和会话语义；先更新契约并联调，保留客户端、权限/错误处理及会话清理，不能整块删除。

构建通过不证明真实 D-01 可用。真实鉴权、通知送达与 D 审计仍需对应组集成。

## 2026-10-27 M3 develop 适配补充

M3 使用同一个公共会话与 HTTP 客户端。显式开发身份增加 `dev-repair-admin`（repair:dispatch、repair:report）、`dev-technician-1`/`dev-technician-2`（repair:work、repair:report），departmentId 均为 null；不授予 room:manage 或 operations:read。已有 seat:reserve 学生身份可报修。身份列表、前端选择器仍归 WEB-D01-IDENTITY 库存，新增 M3 消费登记 WEB-M3-D01。真实 D-01 交付时由 Web/M1/M3 与 M2 联合核验，再清理整个公共开发身份机制；本次未将拟议维修权限或人员目录当作已实现的 D 服务。

共享请求增加 M3 地址与嵌套错误格式兼容；保留 M1/D Problem 错误，同时组合调用方取消、15 秒超时和身份版本检查。详细证据与未完成项见 [M3 集成记录](../../../../../../services/m3/docs/develop-integration.md)。
