# M3 报修工单前端

M3 模块私有页面、业务状态、接口适配与开发联调身份入口。沿用公共 Vue 应用、布局、`ui-*` 样式和图标，没有新增依赖。

## 页面入口

- `/m3`：当前身份可见的工单、状态统计、关键词/状态筛选。
- `/m3/new`：上报故障；只有报修人身份展示此操作。
- `/m3/orders/:id`：工单详情、维修进度、操作记录及当前身份可执行的操作。

所有工单读写使用同源 `/api/m3/v1`。调用契约见 [M3 API](../../../../../contracts/m3-work-orders.md)，实现情况见 [M3 后端](../../../../../services/m3/STATUS.md)。公共 Vite/Nginx 转发由共享工程配置提供；本模块不直接调用 M1，也不内置业务结果。

## 开发运行

先按 [后端 README](../../../../../services/m3/README.md) 启动显式 `M3_MODE=development` 的 M3 服务，再在仓库根目录执行：

```bash
npm --prefix apps/web run dev
```

打开 `/m3`，选择页面上的联调身份。它使用服务器认可的公开合成 token；**仅服务端返回 development 时可选择**。不读取或写入 localStorage/sessionStorage/cookie。浏览器刷新、离开模块或切换身份会清空当前身份和业务数据。

`TEMPORARY-DEPENDENCY TEMP-M3-D-01` 的精确前端清理范围为 `devIdentities.ts`、`ModuleHome.vue` 中开发身份选择与提示、`session.ts` 中开发身份选择逻辑，以及测试中对应的合成身份夹具。业务页面、API 适配器和权限/状态展示逻辑需要保留，后续接入共享身份提供器，不能把本模块 session 当正式 D 登录实现。替换触发和真实联调验收见 [M3 任务方案](../../../../../services/m3/docs/2026-10-26-implementation.md)。

`dependencyMode=stub` 时始终提示“座位联动使用模拟依赖”。`http` 只说明配置的后端会调用 HTTP，不代表真实 M1 验收完成。正式模式或未配置模式显示身份服务未接入，不能选择演示用户。

## 验证

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
node --test apps/web/src/modules/m3/tests/adapter.test.cjs
```

API/session 测试使用 Node 内置测试工具和仓库已有 TypeScript 编译器，仅替换 fetch 网络边界，不替换被测适配器/会话逻辑。真实浏览器流程和验证边界见 [前端实施记录](docs/implementation.md)。
