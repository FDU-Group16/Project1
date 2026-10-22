# `develop` 测试环境自动部署

`develop` 每次推送后，GitHub Actions 的独立 `Staging deployment` 工作流按 `scaffold` → `publish-images` → `deploy-staging` 执行。检查通过后，只构建一次 API 镜像和一次 Web 镜像，发布到 GitHub Container Registry（GHCR）；四个 API 服务复用同一个 API 镜像，通过启动参数选择服务。服务器按不可变 digest 获取缺少的镜像，Docker 复用已有层。SSH 只传本次提交的源码与镜像引用，不再传完整镜像压缩包。部署使用 GitHub `staging` environment，按环境锁串行执行。

目标服务器和端口由 GitHub Secrets 与服务器私有 `.env` 配置，不写入仓库。更换目标服务器后，须重新核验工作流、仓库访问、容器健康状态和外部访问；旧环境的结果不能证明新环境已部署成功。本次镜像复用改动的范围与验证记录见 [任务记录](tasks/2026-10-22-image-reuse.md)。

## 工作流触发范围

| 工作流 | 触发事件 | 执行内容 |
| --- | --- | --- |
| [`CI`](../.github/workflows/ci.yml) | `main/m1/m2/m3` 推送、PR 新建/重开/更新 | 检查及 API/Web 镜像构建，不发布或部署镜像 |
| [`Staging deployment`](../.github/workflows/deploy-staging.yml) | 仅 `develop` 推送 | 检查，通过后构建并发布 API/Web 镜像，再部署该次推送的提交 |

M1 的推送仍由 GitHub runner 自动检查，但不会启动部署工作流，CI 页面也没有“跳过部署”任务。`develop` 的 `push` 事件只启动独立部署工作流；若该分支有未合并 PR，PR 更新事件仍会另行触发 CI。既有 Actions 历史记录会保留；若多个分支共享同一 SHA，提交页面仍可能汇总该提交的其他分支运行状态。方案、验收与验证记录见 [CI 与测试部署分离](tasks/2026-10-22-ci-triggers.md)。

这台服务器作为 GitHub Actions 的自动部署目标。部署负责人完成一次性服务器和 GitHub Secrets 配置后，日常部署、健康检查和失败时的应用回退由工作流执行；其他成员通过各自分支、PR 和 CI 检查参与开发，不需要登录服务器手工验证功能。这里的“GitHub 自动部署”是 GitHub Actions 通过 SSH 部署到服务器，不是 GitHub Pages 托管。

## 服务器准备

1. 准备可通过密钥登录并运行 Docker 的部署用户。当前流水线只发布 `linux/amd64` 镜像，目标须能运行该平台。目标系统须安装 Docker Engine、Docker Compose 插件、`curl` 和 `tar`；按目标系统适用的 Docker 安装说明配置。服务器须能通过 HTTPS 访问 `ghcr.io` 及其镜像层下载所重定向到的 blob 地址；防火墙或代理须允许完整的登录、manifest 与镜像层下载链路。应用镜像由 GitHub runner 构建，PostgreSQL 也从 GHCR 镜像副本获取，服务器无需访问 Docker Hub、PyPI 或 npm。首次部署、镜像层被清理或基础镜像更新时，仍需下载相应层。
2. 以实际部署用户运行 [`scripts/init-staging-env.sh`](../scripts/init-staging-env.sh)，为该用户建立 `$HOME/campus-resource-staging/.env` 并生成随机数据库密码。按服务器网络配置选定 Web 绑定地址和空闲的宿主机端口，再运行：

   ~~~bash
   STAGING_WEB_BIND_ADDRESS="$WEB_BIND_ADDRESS" STAGING_WEB_PORT="$WEB_HOST_PORT" bash scripts/init-staging-env.sh
   ~~~

   私有文件的格式如下：

   ~~~dotenv
   POSTGRES_PASSWORD=<strong-secret>
   STAGING_WEB_BIND_ADDRESS=<server-bind-address>
   STAGING_WEB_PORT=<available-host-port>
   ~~~

   脚本发现既有 `.env` 时不会覆盖。若要调整绑定地址或端口，须在服务器上编辑既有文件，并保留原数据库密码。文件权限须为 `600`。不要把真实 `.env`、私钥或学生数据提交到仓库。
3. 给部署用户配置 SSH 公钥，确认密钥可免交互登录，且用户能运行 `docker compose`。检查 Web 选定的宿主机端口及 API 的 loopback 端口没有被其他服务占用。若 Web 端口冲突，另选空闲端口并同步修改私有 `.env` 和云防火墙规则。公网访问需要在云防火墙或 NAT 放行并映射所选 Web 端口；绑定地址应是公网映射到达的服务器网卡地址。SSH 端口也须允许 GitHub runner 连接。

测试环境 Compose 文件为仓库根目录 [`compose.staging.yaml`](../compose.staging.yaml)。Web 宿主机端口由 `STAGING_WEB_PORT` 配置，默认 `8080`；绑定地址由 `STAGING_WEB_BIND_ADDRESS` 配置，默认只监听 loopback。四个 API 只绑定服务器 loopback；PostgreSQL 不对宿主机发布端口。Web 目前仍是静态外壳；浏览器业务请求需要另行配置 API 路由和访问控制。公网入口目前使用 HTTP，接入身份或真实数据前应先落实 HTTPS 与访问限制。

### 配置 SSH 凭据

部署负责人可以使用已经验证可免口令登录目标机的专用 SSH 密钥。若需新建密钥，在自己的电脑执行以下命令，并把公钥加入部署用户的 `authorized_keys`：

~~~bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/campus_staging_deploy -C github-actions-staging
~~~

通过服务器控制台读取真实主机指纹：`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`。在自己的电脑用 `ssh-keyscan -p "$SSH_PORT" -t ed25519 "$SSH_HOST"` 获取主机公钥，再用 `ssh-keygen -lf` 核对指纹；一致后才将扫描得到的 `known_hosts` 行存入 GitHub Secret。不要把未经核对的扫描结果当成可信主机密钥。私钥只保存在部署负责人自己的电脑和 GitHub Secret 中，绝不写入仓库或日志。

## GitHub 配置

在仓库 Settings → Environments 创建 `staging`，设置以下 Secrets；如果当前仓库套餐不支持 environment secrets，可存放在仓库 Actions Secrets，工作流读取方式相同：

| Secret | 值 |
| --- | --- |
| `STAGING_SSH_HOST` | 目标服务器的 SSH 外部地址 |
| `STAGING_SSH_USER` | 部署用户名 |
| `STAGING_SSH_PRIVATE_KEY` | 与服务器公钥配对的完整 SSH 私钥，保留多行格式 |
| `STAGING_SSH_KNOWN_HOSTS` | 经可信渠道核对指纹后的 OpenSSH `known_hosts` 行 |
| `STAGING_SSH_PORT` | 可选；SSH 非默认端口时填写 |

`STAGING_SSH_HOST` 应与 `known_hosts` 使用的地址一致；非默认 SSH 端口的 `known_hosts` 主机字段使用 `[主机]:端口` 格式。`staging` 环境不需要人工批准；可按团队权限要求限制只有 `develop` 分支能部署。独立部署工作流仅监听 `develop` 的 `push`，其中发布依赖检查成功，部署依赖检查及发布成功；PR 和 `main/m1/m2/m3` 推送只启动 CI 检查。不要将私钥贴进聊天、CI 日志或仓库。

若连接返回 `Permission denied (password)`，而 `ssh -vvv` 显示服务端只允许 `password`，在目标服务器检查实际生效的 `PubkeyAuthentication`、`AuthenticationMethods` 和 `AuthorizedKeysFile` 设置，并核对部署用户家目录、`.ssh`、`authorized_keys` 的归属与权限。修改 SSH 配置时保持当前会话开启；重新加载服务后，从新终端验证密钥登录成功，再关闭旧会话。

### GHCR 权限与构建缓存

工作流使用 GitHub 自动签发的 `GITHUB_TOKEN`，无需新增 Registry Secret。`publish-images` 具有 `packages: write`，`deploy-staging` 只有 `packages: read`；其他任务维持 `contents: read`。组织或仓库须允许工作流创建、写入和读取 Packages。若同名包已存在且没有关联当前仓库，或包不继承仓库访问权限，须由包维护者将当前仓库加入包的 Actions 访问列表并授予所需权限；尤其要检查首次导入的 PostgreSQL 包。API/Web 镜像附带源码仓库与提交标签，部署前仍须核对包实际关联与授权。权限配置以 [GitHub Container Registry 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)和 [Actions 的包访问说明](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)为准。

API/Web 通过 Buildx 使用 GitHub Actions 的持久缓存，分别使用 `staging-api`、`staging-web` scope；普通 CI 使用独立的 `ci-api`、`ci-web` scope。缓存命中时复用构建层，发布和服务器拉取时也复用已存在的镜像层。缓存可能因配额或清理失效；`pull: true` 仍检查上游基础镜像更新，不代表强制重新下载已有层。首次运行需要建立缓存。参见 [Docker 的 GitHub Actions 缓存说明](https://docs.docker.com/build/cache/backends/gha/)与 [镜像拉取说明](https://docs.docker.com/reference/cli/docker/image/pull/)。

## 发布、核验与回退

工作流将应用镜像发布为 `ghcr.io/<小写 owner/repository>-api:<完整提交 SHA>` 和 `-web:<完整提交 SHA>`，将构建返回的不可变 digest 记录在同次运行的 metadata artifact 中，供部署任务读取。artifact 只含记录三个镜像引用的文本文件，不含镜像本体或凭据；这样也避免仓库级短 Secret（如 SSH 端口）可能触发的 job outputs 子串误判与引用丢失。PostgreSQL 上游锁定在 [`docker/staging-postgres-image.txt`](../docker/staging-postgres-image.txt) 的 Linux/amd64 digest；本次查询对应 `18.6-alpine3.24`。[`scripts/publish-staging-postgres.sh`](../scripts/publish-staging-postgres.sh) 使用上游 digest 派生稳定的 GHCR 标签；存在该标签时只查询 manifest，不重复拉取和推送 PostgreSQL。更新数据库镜像须明确修改锁定文件并另行验证兼容性。

[`scripts/deploy-staging-upload.sh`](../scripts/deploy-staging-upload.sh) 将本次提交的 `git archive` 和只含三个 digest 引用的 `images.env` 上传到 `$HOME/campus-resource-staging/releases/<commit SHA>`。Registry 令牌通过 SSH 标准输入传入 [`scripts/pull-staging-images.sh`](../scripts/pull-staging-images.sh)，不写入源码包、`images.env` 或远端命令参数。远端仅在有缺失 digest 时登录，凭据位于权限受限的临时 Docker 配置目录，脚本退出时清理。已有完整 digest 直接复用；缺失的 digest 才执行 `docker pull`，并由 Docker 复用本机已有层。

全部镜像准备成功后，脚本才创建与旧版相同的六个 `campus-resource-<service>:<完整提交 SHA>` 本地别名，再调用 [`scripts/activate-staging.sh`](../scripts/activate-staging.sh)。任一拉取失败不会更新别名或启动新容器。Compose 保留 `--no-build --pull never`，服务器不构建镜像；既有本地 SHA 别名和上一版发布目录仍可用于回退。脚本检查 PostgreSQL、Web 和四个 API 的健康响应，成功后才更新 `current` 符号链接；健康检查失败时尝试使用服务器保留的上一版镜像恢复应用。首次部署没有上一版可供恢复。不要清理正在使用或可能回退到的镜像。激活和回退由工作流环境锁串行化。

日常以 GitHub Actions 中 `deploy-staging` 的结果判断部署是否成功。部署负责人可在服务器上用 `basename "$(readlink -f "$HOME/campus-resource-staging/current")"` 核对已部署的 SHA，按私有 `.env` 中的绑定地址和 Web 端口检查页面，并从外部访问映射后的地址。API 健康端点只在服务器 loopback 上可访问。其他成员无需执行服务器检查。健康检查目前只证明进程可响应，不证明业务功能或数据库读写正确；CI 运行记录和服务器上的提交 SHA 可用于追溯版本。回退演练留待交付阶段安排。

当前尚无业务表和版本化数据库迁移。脚本的应用回退不会回滚 PostgreSQL 数据卷；以后引入迁移时，须先设计新旧应用与 schema 的兼容窗口，并验证空库重放、失败恢复和回退，再把迁移加入自动部署。生产发布、审批和回退流程不由此测试环境工作流承担。
