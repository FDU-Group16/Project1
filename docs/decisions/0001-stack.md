# ADR-0001：项目技术栈与部署边界

- 日期：2026-10-22
- 状态：**proposed / 待组内评审**
- 参与者与达成一致过程：待项目组会议记录补充；本文不代表已有组内共识。

## 背景

课程任务书允许自选技术栈，但要求三个业务模块与公共层共用一套环境，尽早建立自动构建、测试、部署、版本化迁移与可回退发布流程。期末需展示模块间真实网络调用。当前只需基础框架，不实现任何模块功能。用户明确希望采用 Vue + FastAPI，避免在课程项目的当前规模下引入过重的服务框架；组内仍需评审此技术决定。

## 候选方案

| 方案 | 优点 | 此阶段代价 |
| --- | --- | --- |
| Python 3.12 + FastAPI；Vue 3 + Vite | 后端入口简洁；FastAPI 可提供交互式接口文档；前端组件组织直接，适合当前骨架规模 | 前后端使用不同语言；必须以共享 OpenAPI 契约明确跨端字段和错误语义 |
| Node.js + TypeScript + Fastify；Vue 3 + Vite | 后端轻量，前后端可共用 TypeScript 语言 | 多服务目录、契约治理仍需团队组合；不符合用户选定的 Python 后端方向 |
| Java 21 + Spring Boot；Vue 3 + Vite | 依赖管理、健康检查和数据库迁移生态成熟 | 框架和开发环境更重，对当前课程项目的骨架阶段收益有限 |

## 拟采用的决定

- 后端使用 **Python 3.12 + FastAPI + Uvicorn**；前端使用 **Vue 3 + Vite + TypeScript**。
- 采用单仓库，但分开锁定依赖：根目录以 **uv** 管理 Python 项目（`pyproject.toml`、`uv.lock`），`apps/web` 以 **npm** 管理前端（`package-lock.json`）。M1、M2、M3、D 分别使用 `services.m1.main:app`、`services.m2.main:app`、`services.m3.main:app`、`services.d.main:app` 四个独立 ASGI 入口；Web 独立构建。
- 模块间使用带版本路径的 HTTP/JSON 接口；共享契约以仓库中的 **OpenAPI 3.1** 文档为评审依据。先定义调用协议，再实现消费者与提供者。当前重点是 M2/M3 到 M1 的整室状态写回。
- 持久化选择 **PostgreSQL**，每服务独立 schema/账号；迁移与种子数据脚本化。容器部署拟采用 **Docker Compose**，自动化拟采用 **GitHub Actions**。具体迁移工具、反向代理、认证令牌签发及生产审批机制另行决定。

## 理由与影响

四个独立服务满足真实网络集成的展示目标，同时单仓库便于共享契约、流水线和审查历史。FastAPI 的最小应用入口与 Uvicorn 进程适合先搭出可运行服务；uv 统一锁定后端依赖，前端 npm 项目保持独立。前后端语言不同，因此公开接口应以评审过的 OpenAPI 契约为准，不能把框架自动生成的文档视作跨模块协议已获批准。服务不得通过共享数据库绕过接口。不同模块的发布需要兼容的契约版本和协调顺序。

2026-10-22 已运行 `bash scripts/check.sh`：共享契约文件检查、四个 FastAPI 空壳的 HTTP 健康响应、Vue 类型检查和构建均通过；`docker compose config --quiet` 通过。当前本机 Docker 守护进程未启动，容器启动与 GitHub Actions 实际运行未验证。框架检查不能证明业务行为或部署流程。此 ADR 的技术与团队分工仍是提案，需组内评审。

## 待评审问题

1. D 公共层的模块组归属、故障责任和评审人如何确定，并记录组内达成一致的依据？
2. M1 已有个人预约与 M2 整室审批占用冲突时采取何种业务裁决？M2/M3 状态何时对外宣布成功，失败如何补偿？
3. 迁移工具、幂等种子数据、跨服务认证与权限校验采用哪套实现？
4. 仓库的 GitHub 套餐与设置能否提供生产环境 required reviewers？若不能，如何在流水线中实现可审计的人工审批？
5. M2/M3 之外，D 主数据、通知和审计有哪些必须优先定稿的跨模块接口？

## 参考资料

- [FastAPI 入门与自动接口文档](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [Uvicorn 官方文档](https://www.uvicorn.org/)
- [uv 项目依赖与运行命令](https://docs.astral.sh/uv/guides/projects/)
- [Vue 3 项目入门](https://vuejs.org/guide/quick-start.html)
- [Vite 项目指南](https://vite.dev/guide/)
- [OpenAPI 3.1.2 规范](https://spec.openapis.org/oas/v3.1.2.html)
- [Docker Compose 启动就绪依赖](https://docs.docker.com/compose/how-tos/startup-order/)
- [GitHub 部署环境与审批规则](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
