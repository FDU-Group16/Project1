# Web 公共部分状态

- 更新时间：2026-10-22。
- 范围：当前工作区中的公共外壳、布局、组件和路由汇总。M1/M2/M3 各组更新各自目录的 `STATUS.md`；本文件不汇总日常业务进度。
- 关联需求：E-01、E-03、E-04、E-06、E-07、E-08 的工程基础，不表示这些工程要求已经全部验收。

## 当前状态与可用入口

以下描述当前 `m1` 工作树中的业务接入版本；历史静态版本的验证和部署证据在后文单独保留。

| 能力 | 实现情况 | 验证情况 |
| --- | --- | --- |
| [App.vue](src/App.vue) / [main.ts](src/main.ts) | 公共导航、上下文侧栏与 Vue Router；按身份版本及路由路径重建页面，保留独立 M1 示例入口 | 构建与生产游客回归通过；开发身份切换已检查 |
| [router/index.ts](src/router/index.ts) | 汇总 M1/M2/M3/D-02 路由，登录/403/未匹配页、登录恢复、权限显示、标题/滚动/导航焦点 | 游客守卫、安全返回、原有入口回归通过；真实身份提供方待联调 |
| [AppLayout.vue](src/shared/layouts/AppLayout.vue) | 参数化导航、手机菜单、登录入口、跳过导航、开发身份横幅；不导入业务内部 | 桌面、320px 与 Escape 焦点检查通过 |
| [HomePage.vue](src/shared/pages/HomePage.vue)、[LoginPage.vue](src/shared/pages/LoginPage.vue) | 平台首页、真实身份服务登录表单、退出；显式开发模式提供合成身份选择 | 默认入口不会回退模拟登录；真实 D-01 登录/撤销未验证 |
| [AppIcon.vue](src/shared/components/AppIcon.vue)、[ModuleIntro.vue](src/shared/components/ModuleIntro.vue)、[style.css](src/style.css)、[feature.css](src/shared/styles/feature.css) | 图标、主题、模块说明与局部引用表单样式；保留 M2/M3 静态说明范围 | 无新增 UI 依赖；构建与原入口回归通过 |
| [shared/api/client.ts](src/shared/api/client.ts)、[RequestState.vue](src/shared/components/RequestState.vue) | Bearer、15 秒超时、Problem 错误、401 清理、身份变更后的旧响应拒绝；加载/错误/空态展示 | 类型/构建、服务失败态及实际业务页面验收通过；身份切换后旧详情返回404并清空 |
| [shared/auth](src/shared/auth/index.ts) | D 登录/me/logout 消费客户端、sessionStorage、过期和恢复、角色显示；开发身份受双重配置门控 | 生产不显示开发身份；真实 D-01 提供方未接入 |
| [Vite](vite.config.ts) / [Nginx](../../docker/nginx.conf) | 仅将 `/api/m1/api/v1/*` 和 `/api/d/api/v1/*` 转发到对应服务；不转发内部写回 | 实际 API 业务浏览器验收通过，见下方脚本与主任务证据 |

Vue Router 锁定为 `4.6.4`，没有新增状态管理或 UI 组件库。公共代码不导入业务内部；前端页面路由与后端 API 路径分开。身份临时依赖的范围、配置、清理条件见 [实施记录](src/shared/auth/docs/auth-integration.md)。

## 当前版本验证与发布边界

- 类型检查、生产构建和 diff 空白检查通过；父任务已完成根检查、M1/D PostgreSQL 与真实 HTTP 验证，证据见 [M1 实施任务](../../services/m1/tasks/2026-10-22-completion.md)。后端验证不能代替页面端到端验收。
- 当前生产游客/显式预览回归已通过 7 组检查、5 种宽度，无 JavaScript 错误；当前开发 IAB 验证游客重定向、开发标识、502 失败态、身份切换、桌面与 320px 搜索/新建房间表单、菜单 Escape 焦点。
- **真实 API 业务页面验收已通过**：[Playwright脚本](tests/business.browser.cjs)在 `WEB_BUSINESS_TEST=1`、`http://127.0.0.1:5173` 下连接真实API和PostgreSQL、显式使用开发身份，覆盖D房间/座位创建编辑注销、M1插座搜索→预约→取消→再次预约→取消、切换EE读取CS详情404并清空旧数据、学生D管理页403守卫、实际运营统计/M1来源/每日签到码显示；JavaScript错误0。完整证据见[主任务](../../services/m1/tasks/2026-10-22-completion.md)。真实D-01/03/04联调及当前业务部署仍未验证。
- 当前业务版本没有部署、发布 tag 或人工评审证据。分需求提交记录以当前 `m1` Git 历史为准；下方旧版本测试部署不代表当前业务已上线。

## 历史版本验证与发布证据（静态界面与工程骨架）

- 旧静态界面实现 `3593153` 已在 2026-10-22 18:16:31（Asia/Shanghai）通过 [测试部署](https://github.com/FDU-Group16/Project1/actions/runs/39761575377) 健康激活；[线上站点](https://pj1.756888.xyz) 已通过同一 7 组浏览器验收，产物与本地相同。新 Vue 界面可见，真实业务能力仍按模块记录标注。完整 SHA、CI 和外部证据见 [实施记录](docs/vue-interface-implementation.md#提交部署与外部核验)。
- 2026-10-22 旧静态 Vue 界面的根检查及最终生产构建通过；开发服务和生产预览均通过 7 组真实浏览器验收，包含全部入口、筛选/详情/安全返回、键盘和 320–1440px 响应式，无 JavaScript 错误。命令、范围与实际发布证据见 [实施记录](docs/vue-interface-implementation.md)。真实身份和业务接口未接入，不能据此声明业务已验收。
- 旧骨架阶段根目录 `bash scripts/check.sh` 通过，覆盖契约基础检查、后端健康检查、Vue 类型检查和生产构建。
- 旧版浏览器检查与目录重构范围见 [前端骨架任务](docs/frontend-scaffold.md)。该记录包含现有 Vite 依赖告警，升级待单独处理。
- 旧骨架的本机及远端工程证据保留在相应任务和下项；旧静态界面发布以上述历史记录为准。真实业务接口验收、团队人工评审与生产发布尚未登记，未创建 PR 或发布 tag。
- 2026-10-22 镜像复用已随提交 `86679077cd1fcd1dbcd6ace993f3b8d9c6bb4211` 推送到 `develop`，[Staging deployment run 39747752233](https://github.com/FDU-Group16/Project1/actions/runs/39747752233) 全部成功：检查 29 秒、发布 1 分 40 秒、部署 56 秒。API/Web 构建与 GHCR 发布、固定 PostgreSQL 副本发布、服务器只读认证/拉取与健康激活均成功；服务器于 2026-10-22 16:29:43（Asia/Shanghai）报告该提交健康。本次 `bash scripts/check.sh`、9 项部署边界行为测试、关键复用行为破坏对照、Compose 配置、actionlint、工作流结构及 Bash 语法检查通过。源码、完整证据与验证边界见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。未改变前端入口或业务接口，契约及 schema 无变更，无新增迁移；重复运行缓存命中、真实回退、业务与数据库读写、公网 HTTPS 和外部访问尚未验证。

## 依赖与待办

- M1 业务后端和 D-02 主数据接口已经在当前任务实现；真实 PostgreSQL/HTTP 验证见 [M1](../../services/m1/STATUS.md)、[D](../../services/d/STATUS.md)。公共与业务消费字段以 [契约登记](../../contracts/README.md) 为准；提案仍需受影响组评审。
- D-01 真实身份、D-03 通知、D-04 审计提供方不在用户本次授权范围；Web 仅实现身份消费，正常模式依赖真实服务。明确的开发身份库存见 [WEB-D01-IDENTITY](src/shared/auth/docs/auth-integration.md)，不会因真实服务失败自动启用。
- 真实API页面验收已通过，见[业务浏览器脚本](tests/business.browser.cjs)与[主任务](../../services/m1/tasks/2026-10-22-completion.md)；D-01 可用后还需真实登录、恢复、过期、退出、权限和并发旧请求检查，然后按库存移除临时依赖。
- 业务实现与验收分别由 [M1](src/modules/m1/STATUS.md)、[D-02](src/modules/d/STATUS.md)、[M2](src/modules/m2/STATUS.md)、[M3](src/modules/m3/STATUS.md) 记录。M2/M3 仍保持原有模块入口；本轮不实现它们的私有业务。
- 本轮共享变更由父任务集成，M1/D-02/Web 公共维护组、D-01 提供组及受影响模块须在合并前评审；具体人工评审人员未登记。当前仅提交 `m1`，不继承历史任务对 develop 推送或部署的授权。
- GHCR、缓存与测试部署的旧验证保留在下方历史和关联任务；本轮没有重新发布或核验线上业务，不将旧健康激活作为当前上线证据。

## 最近交接

- 2026-10-22：当前 M1/D-02 接入版本新增公共 HTTP、身份消费、路由保护与公开代理，见 [身份实施记录](src/shared/auth/docs/auth-integration.md)。构建、根检查、生产游客回归及[真实API业务浏览器验收](tests/business.browser.cjs)均已通过，详见[主任务](../../services/m1/tasks/2026-10-22-completion.md)；显式开发身份不代表真实D-01联调，当前业务未部署。以下条目保留旧任务历史，不扩展本轮分支与发布授权。

- 2026-10-22：按用户明确授权将原型落地为公共 Vue 界面和 M1 页面，计划同步 m1/develop 并核验测试站点。范围、同步 SHA、共享集成责任、页面验收与发布证据见 [实施记录](docs/vue-interface-implementation.md)。本批实现/验证/部署进度在该记录中分别更新，不代表 D 身份或 M1 后端已完成。

- 2026-10-22：按用户要求保存公共界面方案、M1 页面方案及独立原型，纳入与 D 分工和协作规则一起提交至 m1、develop 的批次。范围、同步证据、原型验证及后续验收见 [设计记录](docs/common-frontend-design.md)。本次 `bash scripts/check.sh` 通过契约检查、四服务健康检查、Vue 类型检查及构建；文档链接检查与 `git diff --check` 通过；对仓库内导出 HTML 的浏览器交互、320/375/768/1024px 布局和明暗主题检查通过，无 JavaScript 错误。证据对应基线 `38ab097` 加本批文件，提交记录以 Git 历史为准；远端流水线结果另行核验。应用业务实现及发布验收范围未改变，设计提交不代表受影响模块已批准。
- 2026-10-22：按用户授权推送镜像复用实现到 `develop`，首次 GHCR 发布、服务器拉取与健康激活成功；保留 develop 门禁、环境锁、提交 SHA 追溯和旧版别名回退兼容。完整运行记录与剩余验证范围见 [镜像复用任务](../../docs/tasks/2026-10-22-image-reuse.md)。
- 2026-10-22：按用户确认保留 M1 自动构建/测试，并将共享测试部署拆为独立的 develop 推送工作流；CI 本身只含检查任务。触发范围、门禁与验证证据见 [共享流水线任务](../../docs/tasks/2026-10-22-ci-triggers.md)，不改变 Web 页面或业务能力。
- 2026-10-22：按用户请求准备将当前改动提交至 `m1` 与 `develop`；已保留 `origin/develop@2892d37` 的部署更新并在实际工作区重跑检查通过。分支、保留检查与验证范围见 [提交准备记录](docs/frontend-scaffold.md#提交准备与分支同步2026-10-22)；人工验收及远端部署仍待登记。
- 2026-10-22：建立模块路由、公共布局与展示组件；各模块可在独立目录继续开发。实现和验证说明见 [任务记录](docs/frontend-scaffold.md)，下一步由带验收标准的业务任务接入实际接口。尚未登记人工验收、提交/PR 或远端发布证据。

## 临时身份与后续集成

本轮没有实现真实身份服务。消费契约为 [D 依赖 v0.1.0 proposed](../../contracts/d-dependencies.md)；明确的本机临时身份及清理库存见 [身份实施记录](src/shared/auth/docs/auth-integration.md)。生产构建不会启用开发身份。真实提供方可用后须经受影响组评审并完成替换验收，不依据临时标记自动删除业务或公共代码。
