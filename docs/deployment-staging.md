# `develop` 测试环境自动部署

`develop` 分支每次推送后，GitHub Actions 先执行 `scaffold` 检查；检查通过才运行 `deploy-staging`，在 GitHub runner 构建镜像并通过 SSH 传给 Linux 服务器，把该提交的 Web、M1、M2、M3、D 和 PostgreSQL 一起部署。工作流使用 GitHub `staging` environment，并串行执行该环境的部署。只有将配置提交到 `develop`、配置好以下密钥并完成服务器准备后，自动部署才会实际运行。首次远端部署仍待验证。

这台服务器只作为 GitHub Actions 的自动部署目标。部署负责人完成一次性服务器和 GitHub Secrets 配置后，日常部署、健康检查和失败时的应用回退由工作流执行；其他成员不需要登录服务器或用它手工验证功能。成员仍通过各自分支、PR 和 CI 检查参与开发。这里的“GitHub 自动部署”是 GitHub Actions 通过 SSH 部署到这台服务器，不是 GitHub Pages 托管。

## 服务器准备

1. 为测试环境准备可通过 SSH 登录并运行 Docker 的部署用户；建议使用专用账号。服务器须安装 Docker Engine、Docker Compose 插件、`curl`、`tar` 和 `gzip`。当前 Ubuntu 20.04 目标机可由负责人以 root 运行 [`scripts/provision-staging-focal.sh`](../scripts/provision-staging-focal.sh) 一次性安装固定版本。日常部署的镜像由 GitHub runner 构建并经 SSH 传入，服务器无需访问 Docker Hub、PyPI 或 npm。
2. 以实际部署用户运行 [`scripts/init-staging-env.sh`](../scripts/init-staging-env.sh)，为该用户建立 `$HOME/campus-resource-staging/.env` 并生成强随机数据库密码。需要通过 NAT 对外提供 Web 时，运行前设置 `STAGING_WEB_BIND_ADDRESS` 为 NAT 到达的服务器内网地址；脚本发现既有 `.env` 时不会覆盖。文件内容如下：

   ```dotenv
   POSTGRES_PASSWORD=<strong-secret>
   STAGING_WEB_BIND_ADDRESS=<server-internal-address>
   ```

   不要将真实 `.env`、私钥或学生数据提交到仓库。脚本创建的 `.env` 权限为 `600`；手工创建时也须设为 `600`。
3. 给部署用户配置专用 SSH 公钥。确认服务器的 SSH 主机公钥指纹，供 GitHub Actions 校验连接。确保服务器端口 8080、3101–3104 未被其他服务占用。

测试环境 Compose 文件为仓库根目录 `compose.staging.yaml`。Web 的 8080 默认只绑定服务器 loopback；本次目标服务器已在私有 `.env` 中设置为 NAT 到达的内网地址，以便通过外部 `10325` 访问。四个 API 的 3101–3104 仍只绑定服务器 loopback；PostgreSQL 不对宿主机发布端口。Web 目前还是静态外壳；浏览器业务请求需要另行配置 API 路由和访问控制。该公网入口使用 HTTP，接入身份或真实数据前应先落实 HTTPS 与访问限制。

当前目标系统是 Ubuntu 20.04。它已[结束标准支持](https://ubuntu.com/20-04)，也不在 Docker [当前支持的 Ubuntu 版本](https://docs.docker.com/engine/install/ubuntu/#os-requirements)中；Docker 保留的 Focal 包只适合此隔离测试环境的过渡使用。服务器能访问国内镜像站，原默认境外源不可达；安装脚本备份 `/etc/apt/sources.list`，改用阿里云 Ubuntu 软件源，并在核对 Docker 官方签名公钥后添加阿里云 Docker Focal 镜像。安装时固定 Engine 28.1.1 与 Compose 2.35.1；不能假定该旧版系统会继续收到 Docker 更新。

### 配置 SSH 凭据

以下命令由部署负责人执行。`deploy@server.example.com` 和 `22` 分别替换为服务器部署用户、**SSH 的外部地址和端口**。GitHub runner 必须能连接这个 SSH 地址和端口；Web 的 NAT 端口 `10325` 不是 SSH 端口。

部署负责人在自己的电脑生成一对仅用于测试部署的密钥。若已有经过验证、可免口令登录目标机的专用密钥，可直接使用，无需再次生成。工作流是无人值守的，私钥只保存在自己的电脑和 GitHub Secret 中：

```bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/campus_staging_deploy -C github-actions-staging
cat ~/.ssh/campus_staging_deploy.pub | ssh -p 22 deploy@server.example.com 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
ssh -i ~/.ssh/campus_staging_deploy -o IdentitiesOnly=yes -p 22 deploy@server.example.com 'docker compose version && command -v curl && command -v tar'
```

通过服务器控制台读取真实主机指纹：`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`。在自己的电脑运行 `ssh-keyscan -p 22 -t ed25519 server.example.com > ~/.ssh/campus_staging_known_hosts`，再用 `ssh-keygen -lf ~/.ssh/campus_staging_known_hosts` 比对指纹；一致后才将该文件内容放入 `STAGING_SSH_KNOWN_HOSTS`。不要把未经核对的扫描结果当成可信主机密钥。

## GitHub 配置

在仓库 Settings → Environments 创建 `staging`，并设置以下 Secrets；如果当前仓库套餐不支持 environment secrets，可存放在仓库 Actions Secrets，工作流读取方式相同：

| Secret | 值 |
| --- | --- |
| `STAGING_SSH_HOST` | 服务器域名或 IPv4 地址 |
| `STAGING_SSH_USER` | 专用部署用户名 |
| `STAGING_SSH_PRIVATE_KEY` | 与服务器公钥配对的专用 SSH 私钥，保留多行格式 |
| `STAGING_SSH_KNOWN_HOSTS` | 经可信渠道核对指纹后的 OpenSSH `known_hosts` 行 |
| `STAGING_SSH_PORT` | 可选；SSH 非默认端口时填写 |

不要直接信任未经核验的 `ssh-keyscan` 输出：先通过可信渠道核对服务器指纹，再保存 `known_hosts` 内容。非默认 SSH 端口的 `known_hosts` 主机字段应使用 `[主机]:端口` 格式。`staging` 环境不需要人工批准；可按团队权限要求限制只有 `develop` 分支能部署。`deploy-staging` 仅在 `develop` 的 `push` 且 `scaffold` 成功后运行，PR 和其他分支只运行检查。

`STAGING_SSH_PRIVATE_KEY` 填所选部署私钥的**完整文本**，保留 `BEGIN`/`END` 行和换行；`STAGING_SSH_KNOWN_HOSTS` 填上一步核对后的文件内容。`STAGING_SSH_HOST` 与 `ssh-keyscan` 使用相同地址，`STAGING_SSH_USER` 填部署用户名，SSH 不在 22 端口时再填 `STAGING_SSH_PORT`。不要将私钥贴进聊天、CI 日志或仓库。

当前目标机的已验证连接使用 `root`。若沿用该账号，`STAGING_SSH_USER` 填 `root`，Secret 私钥使用已经验证可登录的现有密钥；改用专用部署用户时，须先迁移该用户的 SSH 公钥、Docker 权限和私有 `.env`，再更新 Secrets。

若连接返回 `Permission denied (password)`，而 `ssh -vvv` 显示服务端只允许 `password`，先在目标服务器检查实际生效的 `PubkeyAuthentication`、`PermitRootLogin`、`AuthenticationMethods` 和 `AuthorizedKeysFile` 设置，并核对部署用户家目录、`.ssh`、`authorized_keys` 的归属与权限。当前登录会话保持开启，修改 SSH 配置并重新加载服务后，用新的终端验证密钥登录成功，再关闭旧会话。

## 发布、核验与回退

工作流在 GitHub runner 上构建应用镜像、拉取 PostgreSQL 镜像，为六个服务镜像分别标记完整 SHA，再通过 SSH 传给服务器；随后将当前提交的 `git archive` 上传到 `$HOME/campus-resource-staging/releases/<commit SHA>`，调用 `scripts/activate-staging.sh`。远端只使用传入的镜像启动 Compose 服务，不在服务器构建或拉取镜像。脚本检查 PostgreSQL、Web 和四个 API 的健康响应；成功后才更新 `current` 符号链接。健康检查失败时尝试使用服务器保留的上一版镜像恢复应用。首次部署没有上一版可供恢复。不要清理正在使用或可能回退到的镜像。发布过程由工作流环境锁串行化。

日常以 GitHub Actions 中 `deploy-staging` 的结果查看部署是否成功：远端脚本会自动检查 PostgreSQL、Web 和四个 API，失败时让工作流报错并尝试恢复上一版应用。部署负责人首次接入时可在服务器上用 `basename "$(readlink -f "$HOME/campus-resource-staging/current")"` 核对已部署的 SHA；故障排查时可检查 `http://127.0.0.1:8080/` 和 `http://127.0.0.1:3101/healthz` 至 `http://127.0.0.1:3104/healthz`。其他成员无需做这些服务器检查。健康检查目前只证明进程可响应，不证明业务功能或数据库读写正确；CI 运行记录和服务器上的提交 SHA 可用于追溯版本。回退演练留待交付阶段安排。

当前尚无业务表和版本化数据库迁移。脚本的应用回退不会回滚 PostgreSQL 数据卷；以后引入迁移时，须先设计新旧应用与 schema 的兼容窗口，并验证空库重放、失败恢复和回退，再把迁移加入自动部署。生产发布、审批和回退流程不由此测试环境工作流承担。
