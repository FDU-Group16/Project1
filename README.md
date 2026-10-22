# 校园资源服务平台 · 工程骨架

软件过程管理与工程伦理课程 Project 1。当前阶段只搭建协作与运行骨架，没有座位预约、整室审批、报修或公共层业务实现。

## 技术栈

- Python 3.12、FastAPI、Uvicorn：四个有独立 ASGI 入口的轻量 API 服务（M1、M2、M3、D）。
- Vue 3 + Vite + TypeScript：Web 客户端外壳；学生端选 Web，后续按需求实现页面。
- 单仓库分别管理依赖：根目录用 uv 与 `uv.lock` 管理后端，`apps/web` 用 npm 与 `package-lock.json` 管理前端。
- OpenAPI 3.1：跨模块接口的评审契约，以 `contracts/` 为准。
- PostgreSQL 18、Docker Compose：本地基础设施及 `develop` 测试环境部署；服务数据所有权和迁移将在迭代中落地。
- GitHub Actions：提交与拉取请求的依赖安装、前端构建、契约检查和骨架冒烟验证；服务器和密钥配置完成后，`develop` 检查通过会自动部署测试环境。

选择依据、未定事项与方案比较见 [技术决策](docs/decisions/0001-stack.md)；服务边界见 [架构说明](docs/architecture.md)。

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
python -m pip install 'fastapi>=0.158,<0.159' 'uvicorn>=0.30,<1'
npm --prefix apps/web ci
```

然后在两个终端分别启动 M1 和 Web（启动 M1 的终端需先激活 `.venv`）：

```bash
python -m uvicorn services.m1.main:app --host 0.0.0.0 --port 3101
```

```bash
npm --prefix apps/web run dev
```

Web 开发服务地址为 `http://localhost:5173`。其余 API 入口为 `services.m2.main:app`、`services.m3.main:app`、`services.d.main:app`，可分别用端口 3102、3103、3104 启动。当前仅提供 `/healthz` 作为项目健康检查，不代表业务接口已经实现。

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

`scripts/check.sh` 会检查 OpenAPI 文件、四个 FastAPI 空壳的 HTTP 健康响应，以及 Vue 类型检查和构建；没有 uv 时使用 `.venv/bin/python`。pip 安装按 `pyproject.toml` 的版本范围解析依赖，不保证与 `uv.lock` 中的精确版本一致；需要精确复现依赖时使用 uv 或 Docker Compose。

## `develop` 测试环境部署

服务器和 GitHub 密钥由部署负责人完成一次性配置、工作流合入 `develop` 后，该分支每次推送将在检查通过时自动部署完整骨架到 Linux 服务器，并自动执行健康检查。其他成员不需要登录或使用该服务器验证功能。配置与故障排查说明见 [测试环境部署](docs/deployment-staging.md)。首次远端运行仍待验证。

## 协作入口

- [Agent 规则](AGENTS.md)
- [需求基线与状态](docs/requirements.md)
- [实施计划](docs/plan.md)
- [跨模块接口登记](contracts/README.md)
- [D 公共层归属提案](docs/decisions/0002-d-ownership.md)
- [AI 开发任务模板](docs/ai-task-template.md)
- [工程伦理议题记录](docs/ethics-log.md)

`任务书.pdf` 由用户提供、目前未跟踪且未修改。业务代理（DSH 插件）是任务书附加项，本轮不搭建。
