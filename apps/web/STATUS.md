# Web 公共部分状态

- 更新时间：2026-10-22。
- 范围：当前工作区中的公共外壳、布局、组件和路由汇总。M1/M2/M3 各组更新各自目录的 `STATUS.md`；本文件不汇总日常业务进度。
- 关联需求：E-01、E-03、E-04、E-06、E-07、E-08 的工程基础，不表示这些工程要求已经全部验收。

## 当前状态与可用入口

| 能力 | 实现情况 | 验证情况 |
| --- | --- | --- |
| [App.vue](src/App.vue) / [main.ts](src/main.ts) | 组合公共导航、布局与 Vue Router | 类型、构建及本机浏览器检查通过 |
| [router/index.ts](src/router/index.ts) | 首页 `/`、汇总三个模块路由；未知路径回首页 | 首页、模块切换、直达、刷新及前进后退已检查 |
| [AppLayout.vue](src/shared/layouts/AppLayout.vue) | 接收 `navigation: { label: string; to: string }[]`，默认插槽承载页面；提供主导航与跳过导航链接 | 320px 窄屏和键盘跳过导航已检查 |
| [ModuleIntro.vue](src/shared/components/ModuleIntro.vue) | 接收 `title`、`description` 字符串及默认插槽；仅展示内容 | 首页和三个静态模块页已使用并检查 |
| [shared/api](src/shared/api/README.md) | 仅有职责说明 | 无 HTTP 请求实现，不可视为已完成接口接入 |
| [shared/auth](src/shared/auth/README.md) | 仅有职责说明 | 无登录、令牌或权限实现 |

Vue Router 已锁定为 `4.6.4`；没有状态管理或 UI 组件库。公共组件不导入业务模块内部实现。开发/部署 API 代理尚未接入，前端路由 `/m1` 等不是后端 API 路径。

## 验证与发布证据

- 根目录 `bash scripts/check.sh` 通过，覆盖契约基础检查、后端健康检查、Vue 类型检查和生产构建。
- 浏览器检查与本次目录重构范围见 [前端骨架任务](docs/frontend-scaffold.md)。该记录包含现有 Vite 依赖告警，升级待单独处理。
- 上述证据属于本机工作区。人工验收、提交/PR 及测试/生产环境发布记录尚未在本文件中登记，不能据此声称已部署。
- 2026-10-22 镜像复用改动已在工作区准备：develop 先检查，再各构建一次 API/Web 镜像并发布 GHCR；Buildx 使用持久缓存，服务器按 digest 复用镜像和已有层，PostgreSQL 使用固定 digest 的稳定副本。源码入口、权限/网络依赖、检查结果与未验证范围见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。本次 `bash scripts/check.sh`、9 项部署边界行为测试、关键复用行为破坏对照、Compose 配置、actionlint、工作流结构及 Bash 语法检查已通过；新链路的实际镜像构建/推送、服务器拉取、激活和回退尚未验证。未改变前端入口或业务接口，契约及 schema 无变更，无新增迁移。

## 依赖与待办

- 身份、主数据和业务接口依赖相应 [后端模块记录](../../docs/module-status.md)与 [契约](../../contracts/README.md)；当前后端仅有健康端点。
- 登录、公共 HTTP 配置和代理接入须以相应任务和已评审契约实施。
- 各模块页面状态与业务接入分别记录在 [M1](src/modules/m1/STATUS.md)、[M2](src/modules/m2/STATUS.md)、[M3](src/modules/m3/STATUS.md)，公共维护者不代替模块组认定业务完成。
- 镜像复用链路需测试服务器可访问 GHCR 及镜像层 blob HTTPS 地址，并允许当前仓库的 Actions 读写相应 Packages；使用自动 `GITHUB_TOKEN`，无需新增 Registry Secret。用户已确认并授权本次 `develop` 推送及其自动测试部署，推送准备与验证范围见任务记录；远端结果仍待实际核验。共享维护者和 M1/M2/M3/D/Web 各组的具体评审人员、PR、部署版本及发布证据尚未登记。

## 最近交接

- 2026-10-22：按用户请求准备构建一次、持久缓存及 GHCR 层复用，保留 develop 门禁、环境锁、提交 SHA 追溯和旧版别名回退兼容；本地验证和远端未验证范围见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。
- 2026-10-22：按用户确认保留 M1 自动构建/测试，并将共享测试部署拆为独立的 develop 推送工作流；CI 本身只含检查任务。触发范围、门禁与验证证据见 [共享流水线任务](../../docs/tasks/2026-10-22-ci-triggers.md)，不改变 Web 页面或业务能力。
- 2026-10-22：按用户请求准备将当前改动提交至 `m1` 与 `develop`；已保留 `origin/develop@2892d37` 的部署更新并在实际工作区重跑检查通过。分支、保留检查与验证范围见 [提交准备记录](docs/frontend-scaffold.md#提交准备与分支同步2026-10-22)；人工验收及远端部署仍待登记。
- 2026-10-22：建立模块路由、公共布局与展示组件；各模块可在独立目录继续开发。实现和验证说明见 [任务记录](docs/frontend-scaffold.md)，下一步由带验收标准的业务任务接入实际接口。尚未登记人工验收、提交/PR 或远端发布证据。
