# 在现有测试站启用 M3 测试账号

复用 `compose.staging.yaml` 已有 PostgreSQL 18、campus 数据库和 postgres-data 卷，不另建数据库服务，不清空或重置业务数据。此文仅适用于合成数据的课程测试站；正式校园 D-01 仍由 M2 实现。

## 通过既有 GitHub 部署启用

1. 在仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加 `STAGING_TEST_ACCOUNTS_JSON`。值是私下生成的四键密码 JSON：键必须为 `m3-student`、`m3-admin`、`m3-worker1`、`m3-worker2`，值为各自独立的20～128字符随机密码。不要把实际值放入提交、PR、截图、日志或本说明。密码保存在用户的仓库外私有文件中。菜单操作依据 [GitHub 官方说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
2. 在 `m3-develop` 提交本轮改动并 Push，通过新的 PR 合入 `develop`。共享登录、D 适配、数据库初始化和部署配置由相应负责人评审；已有 PR #3 已合并，不会再次自动接收新提交。
3. 等待 **Staging deployment** 成功。本轮部署在原有检查、镜像和 SSH 发布后，仅当上述 Secret 非空才执行测试初始化。首次启用只补缺少的数据库角色/连接和服务令牌，创建 D 002 临时账号表及四个账号；仅房间目录完全为空时使用已有合成房间种子。之后重建 API 和 Nginx，通过网页同源代理逐一验证四个账号、M3 房间/工单访问和退出撤销。
4. 打开 `/login?redirect=/m3`。看到“课程测试账号”提示后，使用私下保存的账号密码。部署日志只有完成状态，没有密码。若初始化失败，该工作流失败；不能只看前面的健康检查说账号已经可用。

**未设置 Secret 时不会创建测试账号。** 本轮代码提交/CI通过也不代表账号已在公网创建。初始化使用现有 staging SSH Secrets，不要求另行分享 SSH 私钥。

| 账号 | 角色 | 可体验功能 |
| --- | --- | --- |
| `m3-student` | 报修人 | 创建、取消本人未开工工单、验收、评价 |
| `m3-admin` | 维修管理员 | 派单、重派、查看超时及符合条件的代验 |
| `m3-worker1` | 维修员一 | 开始/完成分配给自己的维修 |
| `m3-worker2` | 维修员二 | 验证重派后的权限与维修流程 |

流程：报修人创建 → 管理员派单 → 受派维修员开始维修（真实 M1 下架）→ 完工待验收 → 原报修人验收（真实 M1 释放）→ 评价。每次换角色先退出登录；维修参与者不能验收自己的维修。测试管理员沿用全 M3 管理权限，并非仅限某一房间；测试账号不授予空间管理或运维权限。

账号从服务器首次创建起默认7天有效，会话最长2小时；账号有效期不因再次部署而延长。登录每账号15分钟最多5次、站点共100次（包括成功登录）；429需等待窗口结束。重复部署用同一 Secret，不重置已有密码、权限、到期时间。删除 Secret 只停止后续初始化，不能撤销已启用账号。

## 服务器负责人手动入口

本轮版本已部署时，可在服务器运行：

```bash
bash "$HOME/campus-resource-staging/current/scripts/enable-staging-test-accounts.sh" --course-test-site
```

未提供密码输入时随机生成。交付文件为 `$HOME/campus-resource-staging/test-accounts.json`，权限0600，保存在源码目录之外；请私下交付。已有账号但文件丢失时，必须用匹配原密码的 `--credentials-stdin` 恢复交付文件，不自动重置。不能把密码写在命令行参数里。

如果发现 `campus_m1/campus_d/campus_m3` 角色已经存在，而 `.env` 没有对应 URL，脚本会停止并要求补回原连接；不会改密码抢占已有角色。如果配置了外部正式 D_IDENTITY_URL，也会停止，不覆盖真实身份服务。异常中断留下 `.env.test-accounts.pending` 时，该文件包含恢复连接所需秘密，由服务器负责人核对已提交的角色后恢复；不要删文件后盲目重新生成密码。

停用时在服务器 `.env` 将 `D_TEST_ACCOUNTS_ENABLED=0`、`D_APP_ENV=production`，移除 GitHub 测试 Secret，再按原发布入口重建 D API 和 Web。该操作关闭临时登录/身份路由，使测试令牌无法继续通过服务端验证；不要删除业务历史或数据库卷。正式 D-01 替换仍需独立集成验收。

## 验证范围

本轮本机 PostgreSQL 16.2 和真实浏览器证据见 [任务记录](../services/d/tasks/2026-10-27-test-accounts.md)。没有本机 Docker，Docker/PG18 以及服务器首次初始化由 CI/实际部署确认。初始化器调用 PostgreSQL 管理账号仅用于补缺角色/schema，业务进程继续使用各自独立账号；不会将管理账号下放给 API。
