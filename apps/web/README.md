# Web 前端

一个 Vue 应用，由 M1/M2/M3 模块组分别维护业务目录。修改前阅读 [AGENTS.md](AGENTS.md)。

## 当前目录

```text
src/
  modules/
    m1/                  # M1 组
      pages/             # 搜索、预约列表、详情
      components/        # M1 展示组件
      preview/           # 显式只读界面的合成样例
      routes.ts
      README.md
    m2/                  # M2 组，结构同 M1
    m3/                  # M3 组，结构同 M1
  shared/
    components/          # 内联图标、公共状态与模块介绍
    pages/               # 首页、登录入口、403/404
    layouts/AppLayout.vue
    api/README.md
    auth/README.md
  router/index.ts
  App.vue
  main.ts
  style.css
```

尚未实现的模块可用 `.gitkeep` 保留目录。`api.ts` 在首个业务接口获评审并实施时创建，避免把空请求或模拟成功当成接口已实现。

## 运行与接手开发

在仓库根目录执行：

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

访问 `/` 查看新首页，`/m1` 为搜索界面，`/m1/reservations` 为预约列表；这些正常入口明确显示业务服务未接入。`/m1/preview` 及其预约子页面提供显式只读合成样例。`/login` 为身份接入入口，当前不能登录。`/m2`、`/m3` 仍为原有模块说明，另有 `/403` 与未匹配页面。真实登录、业务 API、开发/部署 API 代理仍待相应任务接入。

各组在自己的 `pages/` 创建页面，在 `routes.ts` 添加 `/m1/*`、`/m2/*` 或 `/m3/*` 路由；模块独有组件放入自己的 `components/`。公共导航在 `App.vue` 中组合，公共布局通过参数和插槽使用，不导入模块私有实现。

请求评审前在仓库根目录运行 `bash scripts/check.sh`，并按任务验收条件检查实际页面。本轮 [Vue 界面任务](docs/vue-interface-implementation.md) 记录实现、验证和部署证据；[浏览器验收说明](tests/README.md) 提供运行方式。旧目录重构记录见 [前端骨架任务](docs/frontend-scaffold.md)。
