# Web 前端

一个 Vue 应用，由 M1/M2/M3 模块组分别维护业务目录。修改前阅读 [AGENTS.md](AGENTS.md)。

## 当前目录

```text
src/
  modules/
    m1/                  # M1 组
      pages/ModuleHome.vue
      components/
      routes.ts
      README.md
    m2/                  # M2 组，结构同 M1
    m3/                  # M3 组，结构同 M1
  shared/
    components/ModuleIntro.vue
    layouts/AppLayout.vue
    api/README.md
    auth/README.md
  router/index.ts
  App.vue
  main.ts
  style.css
```

各模块的 `components/` 用 `.gitkeep` 保留；有实际组件后可删除该文件。`api.ts` 在首个业务接口获评审并实施时创建，避免把空请求或模拟成功当成接口已实现。

## 运行与接手开发

在仓库根目录执行：

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

访问 `/`、`/m1`、`/m2`、`/m3`，可切换首页与三个模块说明页。业务尚未实现，登录、业务 API、开发/部署 API 代理仍待相应任务接入。

各组在自己的 `pages/` 创建页面，在 `routes.ts` 添加 `/m1/*`、`/m2/*` 或 `/m3/*` 路由；模块独有组件放入自己的 `components/`。公共导航在 `App.vue` 中组合，公共布局通过参数和插槽使用，不导入模块私有实现。

请求评审前在仓库根目录运行 `bash scripts/check.sh`，并按任务验收条件检查实际页面。目录重构的范围、方案和验证记录见 [前端骨架任务](docs/frontend-scaffold.md)。
