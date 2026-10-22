# develop 部署镜像复用

日期：2026-10-22。关联需求：E-03、E-04、E-06、E-07、E-08。按 [AI 任务模板](../ai-task-template.md)记录范围、同步、验收和交接。

## 目标与范围

- 用户要求按建议修改：每次 develop 部署只构建一次 API/Web 镜像，跨运行复用构建缓存，复用不变的 PostgreSQL，并避免把服务器已有的镜像层再次整包传输。
- 共享依赖为 Web 与 M1/M2/M3/D 共用的 CI、镜像构建和测试部署基础设施。允许修改 `.github/workflows/`、部署相关 `scripts/` 及其针对性行为测试、`docker/` 镜像输入、`compose.staging.yaml`、本记录、`docs/deployment-staging.md`、`docs/requirements.md`、`apps/web/STATUS.md`。
- 不实现业务端点，不改变业务契约、schema、数据库卷或页面入口，不升级应用依赖；不修改其他业务模块记录。当前跨模块业务契约仍是 `proposed`，本任务不依赖这些端点。
- 集成准备由本次请求操作者通过 Codex 完成；共享 CI/部署维护者及受影响的 M1/M2/M3/D/Web 各组负责人工评审，具体人员及结果未知。实现阶段只准备工作区改动；用户后续明确确认并授权推送到 `develop`，包含该推送触发的既有测试环境部署，不包含生产发布。

## 协作与 develop 同步

- 因修改共用部署基础设施触发 develop 同步。工作区：`/Users/chen/Documents/课程/软件过程管理/Project1`；工作分支 `m1`；初始 HEAD `9cf5d986d805e08a56145c6cf342f27dc3993001`。
- 已确认团队远程 `origin` 为 `https://github.com/FDU-Group16/Project1.git`；初始工作区干净，无冲突或未完成 Git 操作。范围先记录，再获取远程。
- 2026-10-22 16:03–16:05（Asia/Shanghai）成功获取 `origin/develop`，确认 SHA 为 `9cf5d986d805e08a56145c6cf342f27dc3993001`，已为 HEAD 的祖先，无须分支更新；结果 HEAD 同为上述 SHA。
- 已读取根/Web `AGENTS.md`、`docs/module-status.md`、`apps/web/STATUS.md`、部署文档与既有 CI 交接，并核对契约状态。实际验证基于上述 HEAD 加本任务工作区改动，未把远程引用当作本地实现或发布证据。
- 推送准备：2026-10-22 16:21（Asia/Shanghai）按用户授权再次获取并确认 `origin/develop@9cf5d986d805e08a56145c6cf342f27dc3993001`，仍与本地 HEAD 一致。无未完成 Git 操作或冲突；现有 `develop` 分支同样位于该提交，已安全切换到 `develop` 并保留全部 11 个任务文件，未合并其他分支。提交前再次通过 9 项行为测试、actionlint、脚本语法及差异检查；本次提交由包含此记录的 Git 历史追溯。

## 方案与兼容性

1. `scaffold` 保留检查门禁；`publish-images` 在检查成功后各构建并发布一次 API/Web，使用分开的 `staging-api`/`staging-web` GitHub Actions BuildKit 缓存。普通 CI 仍验证镜像构建，缓存分别为 `ci-api`/`ci-web`。四个 API 服务共用同一个 API 镜像。
2. 发布任务使用 `packages: write`，部署任务仅用 `packages: read`；两者使用自动 `GITHUB_TOKEN`，不新增 Registry Secret。保留 SHA 标签供追溯，实际部署采用构建返回的不可变 digest。三个镜像引用经同次运行的 metadata artifact 文本文件传给部署任务，不包含镜像本体或 token；避免仓库级短 Secret（例如 SSH 端口 `22`）在 GitHub 子串检查中误判并过滤跨 job outputs。
3. PostgreSQL 上游固定于 [`docker/staging-postgres-image.txt`](../../docker/staging-postgres-image.txt)：`docker.io/library/postgres:18-alpine@sha256:3b0ef735388b2cb097fc29b8bb421d86d57d0ddbe7aa1fbd6493e06d65028503`。查询时为 Linux/amd64 的 `18.6-alpine3.24`。GHCR 副本标签由上游 digest 派生，存在时不再拉取/推送；升级须明确更新锁定文件并验证兼容性。
4. SSH 仅上传发布源码与三个 digest 的 `images.env`。只读令牌经 SSH 标准输入送到远端，用于临时 Docker 登录配置；不进入源码包、镜像元数据或远端命令参数。完整 digest 已在本机时直接复用；否则拉取缺少的 digest，由 Docker 复用已有层。
5. 所有镜像准备成功后才创建六个原格式的本地 SHA 别名，再调用既有激活脚本。拉取失败不改变发布别名或启动容器。保留 develop 专用触发、`staging` 环境、部署并发锁、健康检查、`--no-build --pull never`、上一版回退与原数据库卷。

备选是继续经 SSH 传完整镜像归档，可避免服务器访问 GHCR，但会重复传输已有层。选择 GHCR 符合本次复用目标，条件是服务器可访问 GHCR 及 blob HTTPS 下载链路，且组织/包允许当前仓库的 Actions 读写；既有包须检查仓库关联与访问授权。下述首次运行已验证当前环境的发布、认证与拉取链路；首次运行、缓存失效或新增镜像层仍需下载。

## 验收与验证

- 可观察条件：develop 检查成功后 API/Web 各构建一次；API/Web 缓存互不覆盖；PostgreSQL 重复发布跳过下载/推送；服务器只拉缺失 digest；全部准备完成前不改别名或激活；凭据临时保存并清理；保留触发门禁、环境锁、提交追溯和旧发布回退兼容。
- `bash scripts/check.sh` 已完整通过：契约基础检查、四个服务的真实 HTTP 健康响应、Vue 类型检查与生产构建。初次运行因沙箱限制本地 socket 失败，获准重跑后通过。
- `python3 scripts/test-staging-images.py` 的 9 项行为测试通过：执行实际脚本，替换 Docker/SSH/Git 外部边界，覆盖 PostgreSQL 重复发布、已有/缺失 digest、拉取/登录失败、digest 校验、临时凭据清理、源码/元数据上传及激活门禁。临时副本将本地复用条件破坏为 `if false` 后，`test_existing_local_digests_are_reused` 按预期失败；原文件未改。
- `DEPLOY_SHA=9cf5d986d805e08a56145c6cf342f27dc3993001 docker compose --env-file .env.example -f compose.staging.yaml config --quiet`、三个部署脚本的 `bash -n` 和 `git diff --check` 已通过。
- metadata artifact 方案落地后，actionlint `1.7.12` 检查两份工作流零错误；Python YAML 结构检查确认触发范围、检查/发布/部署门禁、API/Web 各一次构建、缓存 scope、读写权限、artifact 上传下载名称一致、覆盖及缺文件报错配置、digest 来源，全部 `run` 内容的 Bash 语法检查通过。
- 本机 Docker daemon 不可用，因此本机未实际构建/推送镜像；外部命令边界测试本身不代表真实 GHCR 联调。实际镜像构建/发布、服务器认证/拉取与健康激活现已由下述 GitHub Actions 运行验证；真实回退演练仍未执行。
- 既有基线 [GitHub staging run 39744555956](https://github.com/FDU-Group16/Project1/actions/runs/39744555956) 在 `9cf5d986d805e08a56145c6cf342f27dc3993001` 成功；它运行的是改动前的链路，不作为本次 GHCR 实现的部署证据。

## 首次新链路部署证据

- 用户授权后，已将实现提交 [`86679077cd1fcd1dbcd6ace993f3b8d9c6bb4211`](https://github.com/FDU-Group16/Project1/commit/86679077cd1fcd1dbcd6ace993f3b8d9c6bb4211) 推送到 `develop`；触发的 [Staging deployment run 39747752233](https://github.com/FDU-Group16/Project1/actions/runs/39747752233) 全部成功：`Validate staging` 29 秒，`Publish staging images` 1 分 40 秒，`Deploy staging` 56 秒。
- 本次运行成功构建并发布 API/Web 镜像、发布固定 PostgreSQL 副本到 GHCR，经同次运行的 metadata artifact 传递引用；服务器使用部署任务的只读包令牌完成 GHCR 登录和镜像拉取，并成功激活。由此确认本次环境的包读写权限及镜像下载链路可用。
- API 与 Web 的持久缓存导出均成功：API 日志为 `sending cache export 13.6s done`，Web 为 `sending cache export 24.5s done`（导出步骤共 26.8 秒）。本轮未出现 `CACHED`，只证明缓存已写入，不证明跨运行命中。三个引用文件的 metadata artifact 共 663 字节，已成功传到部署任务。
- 服务器日志于 2026-10-22 16:29:43（Asia/Shanghai）记录 `Staging is healthy at commit 86679077cd1fcd1dbcd6ace993f3b8d9c6bb4211`，对应 PostgreSQL、Web 与四个 API 的既有健康检查通过。它不证明业务功能、数据库读写、公网 HTTPS 或外部访问已验收。
- 重复运行的真实缓存命中、PostgreSQL 发布跳过与服务器镜像复用仍待后续运行确认；真实回退演练未执行。本记录只确认上述首次运行，不预填后续文档推送的运行结果。

## 交接与下一步

- 实现入口：[部署工作流](../../.github/workflows/deploy-staging.yml)、[普通 CI](../../.github/workflows/ci.yml)、[PostgreSQL 发布](../../scripts/publish-staging-postgres.sh)、[远端镜像准备](../../scripts/pull-staging-images.sh)、[源码上传与激活](../../scripts/deploy-staging-upload.sh)、[行为测试](../../scripts/test-staging-images.py)。操作说明见 [部署文档](../deployment-staging.md)，公共状态见 [Web STATUS](../../apps/web/STATUS.md)，需求追溯已更新至 [需求基线](../requirements.md)。
- 实现已推送到 `develop` 并在 `staging` 环境健康激活，提交与运行证据如上。未创建 PR，团队评审与发布 tag 尚未登记；无新增 schema 迁移，不改变业务契约版本或各业务模块的可用能力。
- 下一步通过后续文档推送验证重复运行的构建缓存、PostgreSQL 复用和实际缺层传输，并核对健康状态与部署 SHA；结果待实际运行后登记。真实回退演练、业务与数据库读写、公网 HTTPS 和外部访问继续按相应任务验收。
