# 校园资源服务平台

软件过程管理与工程伦理课程 Project 1。当前 `m1` 分支已实现 M1 座位预约及 D-02 房间/座位主数据；M2、M3 和 D 的其他子域仍按各自交接记录继续开发。

## 技术栈

- Python 3.12、FastAPI、Uvicorn：四个有独立 ASGI 入口的轻量 API 服务（M1、M2、M3、D）。
- Vue 3 + Vite + TypeScript：统一 Web 客户端，含 M1 学生/管理流程和 D-02 管理页面。
- 单仓库分别管理依赖：根目录用 uv 与 `uv.lock` 管理后端，`apps/web` 用 npm 与 `package-lock.json` 管理前端。
- OpenAPI 3.1：跨模块接口的评审契约，以 `contracts/` 为准。
- PostgreSQL 18、Docker Compose：本地基础设施及 `develop` 测试环境部署；M1/D-02 使用独立 schema/账号和版本迁移。
- GitHub Actions：依赖安装、前端构建、契约、健康及业务检查；`develop` 的测试部署仍需按业务依赖配置集成。

选择依据、未定事项与方案比较见 [技术决策](docs/decisions/0001-stack.md)；服务边界见 [架构说明](docs/architecture.md)。

## M1 与 D-02 本地业务演示

当前 `m1` 分支已实现 M1 预约/签到/提醒调度/历史/运营/写回提供方和 D-02 主数据。D-01 身份、D-03 通知、D-04 审计保留接口依赖；普通模式失败关闭，不会自动进入演示模式。其他业务模块和部署完成程度见各自状态。

在本分支工作区安装 Python 3.12、uv、Node.js/npm，并启动 Docker 后：

```bash
uv sync --frozen
npm --prefix apps/web ci
uv run python -m services.m1.temporary_dependencies.run_demo
```

该显式开发命令生成忽略的随机凭据，创建并保留本机 PostgreSQL，重放 M1/D 各自迁移、幂等导入合成房间/座位，并启动 D、M1、调度器和 Web。浏览器打开 <http://127.0.0.1:5173>，登录页选择合成学生/房间管理员/运营身份。身份和通知/审计是明确标注的开发替身，主数据和预约使用真实 HTTP 与 PostgreSQL。Ctrl+C 停止本次服务，保留数据库；不要删除 `.env.m1-development.json` 后继续使用旧数据库容器。

正常配置、提供方缺口及替换说明见 [M1 README](services/m1/README.md)、[D-02 README](services/d/README.md)和[验收计划](services/m1/tasks/2026-10-22-completion.md)。根统一检查现在会创建并删除独立 PostgreSQL 测试容器，验证实际业务、HTTP 集成、账号隔离与关键行为变异，再执行 Vue 检查和构建：

```bash
bash scripts/check.sh
```

以下原有 Compose/单服务命令仍可运行工程骨架；其发布配置尚未配置新业务数据库、D 身份提供方和调度进程，不能当作本次业务部署完成。

## 运行项目

只安装 Docker 的同学可在项目根目录启动全部服务，本机无需安装 Python、uv 或 Node.js：

```bash
cp .env.example .env
docker compose up --build
```

Web 地址为 `http://localhost:8080`，四个 API 的 `/healthz` 地址为 `http://localhost:3101/healthz` 至 `http://localhost:3104/healthz`。PostgreSQL 映射到本机 5433。按 `Ctrl+C` 停止，随后可运行 `docker compose down` 清理容器。

本机开发需要 Python 3.12、Node.js 24 和 npm。没有 uv 时，可以用 Python 自带的 venv 和 pip 安装后端依赖：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install 'fastapi>=0.158,<0.159' 'uvicorn>=0.30,<1' 'psycopg[binary]>=3.2,<4' 'httpx>=0.28,<1'
npm --prefix apps/web ci
```

然后在两个终端分别启动 M1 和 Web（启动 M1 的终端需先激活 `.venv`）：

```bash
python -m uvicorn services.m1.main:app --host 0.0.0.0 --port 3101
```

```bash
npm --prefix apps/web run dev
```

Web 开发服务地址为 `http://localhost:5173`。其余 API 入口为 `services.m2.main:app`、`services.m3.main:app`、`services.d.main:app`，可分别用端口 3102、3103、3104 启动。未配置业务数据库和真实依赖时，M1/D 的 `/healthz` 仍可响应，但业务请求会失败；需要本机业务演示时使用上方显式启动器。

若已安装 uv，可用锁文件安装后端依赖，并用相同方式启动服务：

```bash
uv sync --frozen
npm --prefix apps/web ci
uv run uvicorn services.m1.main:app --host 0.0.0.0 --port 3101
```

## 本地验证

安装依赖后运行统一检查：

```bash
bash scripts/check.sh
```

`scripts/check.sh` 检查 OpenAPI、四服务 HTTP 健康响应、隔离 PostgreSQL 上的 M1/D-02 业务及跨服务行为、关键行为变异、Vue 类型和构建。需启动 Docker；测试容器结束后自动移除。没有 uv 时使用 `.venv/bin/python`。pip 安装按版本范围解析依赖，不保证与 `uv.lock` 一致；精确复现请使用 uv。

## `develop` 测试环境部署

`develop` 测试部署工作流将检查通过的代码部署到 Linux 服务器并执行健康检查，配置与故障排查见 [测试环境部署](docs/deployment-staging.md)。既有静态界面部署证据见 [Web 交接](apps/web/STATUS.md)；本轮 M1/D-02 未推送或部署，发布前需配置独立数据库、真实身份/通知/审计提供方和调度进程并完成联调。

## 协作入口

- [Agent 规则](AGENTS.md)
- [需求基线与状态](docs/requirements.md)
- [模块完成记录与 Agent 交接入口](docs/module-status.md)
- [实施计划](docs/plan.md)
- [跨模块接口登记](contracts/README.md)
- [D 公共层归属提案](docs/decisions/0002-d-ownership.md)
- [AI 开发任务模板](docs/ai-task-template.md)
- [工程伦理议题记录](docs/ethics-log.md)

`任务书.pdf` 是已纳入版本管理的课程依据，本轮未修改。业务代理（DSH 插件）是任务书附加项，本轮不搭建。
