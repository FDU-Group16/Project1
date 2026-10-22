# 浏览器界面验收

`interface.browser.cjs` 对真实 Vite 生产预览或已部署站点执行浏览器交互，不替换应用逻辑或拦截接口。覆盖页面直达/刷新、导航、正常/示例状态、筛选、预约展示、登录安全返回、键盘和窄屏。

前置：可用的 Node.js、Playwright 和 Chrome。Playwright 可使用已有开发工具环境或安装在仓库外的临时目录；不属于应用运行依赖，不修改 npm 锁文件。

```sh
# 在 apps/web 中构建并启动生产预览
npm run build
npm exec -- vite preview --host 127.0.0.1 --port 4187 --strictPort

# 在仓库根目录的另一个终端运行；NODE_PATH 指向已安装 Playwright 的 node_modules
NODE_PATH=/path/to/node_modules node apps/web/tests/interface.browser.cjs http://127.0.0.1:4187
```

参数可替换为测试站点 URL。设置 `WEB_SCREENSHOT_DIR` 可保存截图供人工检查；`WEB_BROWSER_CHANNEL` 可覆盖默认的 `chrome` 通道。截图不代表完整屏幕阅读器或真实业务 API 验收。此脚本限定未登录生产界面与只读示例，不提交登录或业务写操作；生产环境不能出现开发身份入口。实时业务验收必须使用明确的本机合成数据环境，覆盖 M1 与 D-02 的真实 HTTP 操作。

## 本机真实业务流程

先在独立测试工作区运行根 README 中的显式开发启动器，再运行：

```sh
WEB_BUSINESS_TEST=1 NODE_PATH=/path/to/node_modules node apps/web/tests/business.browser.cjs http://127.0.0.1:5173
```

脚本只接受 localhost/127.0.0.1，要求显式确认使用合成数据，且页面必须启用开发身份。它通过实际界面创建专用房间/座位，完成修改、搜索、预约、取消、再次预约、切换身份隔离、统计/来源/编码展示和注销；没有接口拦截或假业务响应。成功后保留已注销资源和已取消预约作为历史，失败时可能留下带 `UI verification` 前缀的合成资源，请在测试库处理，勿对真实数据环境运行。它不验证未来时段的实际签到或真实身份/通知/审计提供方；签到和调度时间边界由后端行为测试覆盖。

2026-10-22：上述本机业务流程全部通过，JavaScript 错误为 0。生产界面脚本另通过 7 组检查及 5 种屏幕宽度；综合证据见 [M1/D-02 主任务](../../../services/m1/tasks/2026-10-22-completion.md)。
