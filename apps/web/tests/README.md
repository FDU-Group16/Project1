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

参数可替换为测试站点 URL。设置 `WEB_SCREENSHOT_DIR` 可保存截图供人工检查；`WEB_BROWSER_CHANNEL` 可覆盖默认的 `chrome` 通道。截图不代表完整屏幕阅读器或真实业务 API 验收。全部写入操作在本批页面中均不可用，线上测试只浏览和操作本地显示状态。
