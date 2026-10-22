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
- 上述页面与浏览器证据属于本机工作区；远端工程部署证据见下项，不表示业务页面或接口已经验收。人工评审与生产发布尚未登记，未创建 PR 或发布 tag。
- 2026-10-22 镜像复用已随提交 `86679077cd1fcd1dbcd6ace993f3b8d9c6bb4211` 推送到 `develop`，[Staging deployment run 39747752233](https://github.com/FDU-Group16/Project1/actions/runs/39747752233) 全部成功：检查 29 秒、发布 1 分 40 秒、部署 56 秒。API/Web 构建与 GHCR 发布、固定 PostgreSQL 副本发布、服务器只读认证/拉取与健康激活均成功；服务器于 2026-10-22 16:29:43（Asia/Shanghai）报告该提交健康。本次 `bash scripts/check.sh`、9 项部署边界行为测试、关键复用行为破坏对照、Compose 配置、actionlint、工作流结构及 Bash 语法检查通过。源码、完整证据与验证边界见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。未改变前端入口或业务接口，契约及 schema 无变更，无新增迁移；重复运行缓存命中、真实回退、业务与数据库读写、公网 HTTPS 和外部访问尚未验证。

## 依赖与待办

- 身份、主数据和业务接口依赖相应 [后端模块记录](../../docs/module-status.md)与 [契约](../../contracts/README.md)；当前后端仅有健康端点。
- 登录、公共 HTTP 配置和代理接入须以相应任务和已评审契约实施。
- 已整理 [通用前端设计](docs/common-frontend-design.md) 与 [独立交互原型](docs/prototypes/common-frontend.html)，覆盖公共外壳、视觉规范、登录状态与 M1 示例页面。关联 D-01、E-01、E-07、E-09；当前仅为提案/原型，未替换 Vue 外壳，未新增业务路由、接口、契约或迁移。真实身份与接口联调尚未验证，维护与评审人员仍需在实施任务中确认。
- 各模块页面状态与业务接入分别记录在 [M1](src/modules/m1/STATUS.md)、[M2](src/modules/m2/STATUS.md)、[M3](src/modules/m3/STATUS.md)，公共维护者不代替模块组认定业务完成。
- 当前测试环境的 GHCR 网络、包读写与部署任务只读令牌已由首次运行验证，API/Web 持久缓存已成功导出；更换环境仍须核验 GHCR/blob HTTPS 访问及包授权。使用自动 `GITHUB_TOKEN`，无需新增 Registry Secret。下一步通过后续文档推送验证重复运行的缓存和镜像复用；不得提前将结果视为通过。共享维护者和 M1/M2/M3/D/Web 各组的具体评审人员尚未登记。

## 最近交接

- 2026-10-22：按用户要求保存公共界面方案、M1 页面方案及独立原型，纳入与 D 分工和协作规则一起提交至 m1、develop 的批次。范围、同步证据、原型验证及后续验收见 [设计记录](docs/common-frontend-design.md)。本次 `bash scripts/check.sh` 通过契约检查、四服务健康检查、Vue 类型检查及构建；文档链接检查与 `git diff --check` 通过；对仓库内导出 HTML 的浏览器交互、320/375/768/1024px 布局和明暗主题检查通过，无 JavaScript 错误。证据对应基线 `38ab097` 加本批文件，提交记录以 Git 历史为准；远端流水线结果另行核验。应用业务实现及发布验收范围未改变，设计提交不代表受影响模块已批准。
- 2026-10-22：按用户授权推送镜像复用实现到 `develop`，首次 GHCR 发布、服务器拉取与健康激活成功；保留 develop 门禁、环境锁、提交 SHA 追溯和旧版别名回退兼容。完整运行记录与剩余验证范围见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。
- 2026-10-22：按用户确认保留 M1 自动构建/测试，并将共享测试部署拆为独立的 develop 推送工作流；CI 本身只含检查任务。触发范围、门禁与验证证据见 [共享流水线任务](../../docs/tasks/2026-10-22-ci-triggers.md)，不改变 Web 页面或业务能力。
- 2026-10-22：按用户请求准备将当前改动提交至 `m1` 与 `develop`；已保留 `origin/develop@2892d37` 的部署更新并在实际工作区重跑检查通过。分支、保留检查与验证范围见 [提交准备记录](docs/frontend-scaffold.md#提交准备与分支同步2026-10-22)；人工验收及远端部署仍待登记。
- 2026-10-22：建立模块路由、公共布局与展示组件；各模块可在独立目录继续开发。实现和验证说明见 [任务记录](docs/frontend-scaffold.md)，下一步由带验收标准的业务任务接入实际接口。尚未登记人工验收、提交/PR 或远端发布证据。
