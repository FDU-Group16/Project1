# M2 前端准备与 develop 集成任务

日期：2026-10-29（Asia/Shanghai）
状态：WEB-M2-01 已单独提交并上传；WEB-M2-02 技术检查通过，待提交。真实业务和 develop 部署未验收

## 协作需求与同步

- 用户要求参照 `develop` 的 README，把 M2 同步到 `develop` 并完善 M2 前端，分批提交。固定本地工作区为 `E:\Codex\M2project`，当前写入分支 `m2`。
- 已抓取 `origin/m2@a60609dff131e4e95227f96562d9cebc8ff82418` 与 `origin/develop@50ccf95f1fda292c907a3d1907f1c99f5b99f012`。共同祖先为 `99ce858a2bbf8caa2f4b226a83f989c54d6992d1`；两分支分别领先共同祖先 10、26 个提交。`develop` 不是 `m2` 的快进目标，根规则要求分叉由人集成，不自动合并、重放或覆盖。工作区只有 `m2` 一个 Git worktree；没有已确认的独立 `develop` 目录。
- 本地 `m2` 原为干净的 `29d0f5b`，已安全快进至远端 `a60609d`，没有合并提交。需保留 `develop` 的 M1、D、共享认证、代理与部署改动；只读参考 `origin/develop:README.md`、根/Web 规则及共享客户端。M2 前端代码只在本模块目录编写，集成后由团队评审兼容性。
- `origin/m2` 的 A1-02 只完成核心申请持久化与防重，尚无公开 M2 业务 HTTP、审批状态/端口或正式装配；`develop` README 也注明新业务部署可用性未验证。前端不得假造已提交申请、审批成功或后端数据。

## 目标与分批范围

- 关联需求：`M2-01`、`M2-02`、`M2-03`、`E-01`、`E-07`。
- 批次 WEB-M2-01：建立申请草稿的本地校验与预览页，只转换拟议 `ApplicationCreate` 的五个字段为 UTC；不发送请求、不持久保存、不接受客户端身份或审批字段。允许修改 `apps/web/src/modules/m2/draft.ts`、`pages/DraftPage.vue`、`routes.ts`、`tests/draft.test.mjs`、`tests/draft.browser.cjs`、本任务、`STATUS.md`。
- 批次 WEB-M2-02：把 `/m2` 首页改为清晰的模块入口和能力边界，导航到草稿页，并说明审批、查询与真实提交尚未开放。允许修改 `apps/web/src/modules/m2/pages/ModuleHome.vue`、`tests/home.browser.cjs`、`README.md`、本任务、`STATUS.md`；如需调整范围先记录原因。
- 不修改其他业务模块、共享认证/API/布局、根路由、全局样式、依赖/锁文件、后端或部署配置。不使用替身；页面不提供模拟成功回执。

## 方案与验收

- 草稿页用浏览器本地日期时间输入，在客户端检查房间 ID 非空、用途去首尾空白且不超过 500 字、人数为正整数、开始时间在未来、结束晚于开始。仅在预览时生成 UTC ISO 时间；最终资格、容量、权限和政策仍由未来后端负责。
- 页面使用明确的“本地预览”标识、重置与字段错误提示；不写 localStorage，不发网络请求。窄屏与键盘可操作，状态文案不会把草稿称为已申请。
- 验证纯校验函数的正常/空白/非法人数/时间顺序/UTC 转换；Vue 类型检查和构建；根 `bash scripts/check.sh` 在可用的隔离环境执行。当前 `develop` 的根检查包含 Docker/PostgreSQL；若本机不可执行，准确标注未通过的环境门槛，不补造结果。
- 关键故障注入：去掉整数检查或时间顺序检查时，对应测试应失败。
- 交接更新本模块 `STATUS.md`；真实接口、审批、M1/D 联调、团队 Review、`develop` 合入及测试部署单独标为未验证。需要团队评审分叉集成与共享客户端兼容性，不能由本任务把 `m2` 整分支覆盖 `develop`。

## WEB-M2-01 实际检查

- `node --test apps/web/src/modules/m2/tests/draft.test.mjs`：5/5 PASS，覆盖五字段形状、UTC 转换、空白、非法人数、过去/逆序/无效时间和用途上限。
- `npm --prefix apps/web run typecheck`：PASS。首次非提权构建因沙箱不能写 Vite 临时文件而失败；在获准的工作区权限下重跑 `npm --prefix apps/web run build`：PASS。
- `bash scripts/check.sh`：PASS，显式使用仓库隔离的 uv 和本进程 UTF-8/时区环境；四个健康检查端口在启动前均空闲。脚本不覆盖本页的真实浏览器交互或 M2 业务 API。
- `NODE_PATH=<Codex 捆绑 Node 模块> WEB_BROWSER_CHANNEL=msedge node apps/web/src/modules/m2/tests/draft.browser.cjs http://127.0.0.1:4187`：本地 Vite 预览 PASS，覆盖直接访问/刷新、空白字段焦点与提示、五字段预览、UTC 标识、无 `/api/` 请求、重置、320px 无横向溢出、键盘焦点与无页面异常。系统 Chrome 与当前捆绑 Playwright 协议不兼容，捆绑 Chromium 未安装；改用本机 Edge 通过，无需全局安装。
- 本批尚未形成提交、push、PR、人工评审或部署证据；结果以之后实际 Git/CI 为准。

WEB-M2-01 后续 Git 证据：提交 `9cfaedb8221f1793f98e70a7b7c4cdbb6d6ef19e` 已从 `a60609d` 普通推送至 `origin/m2`；未推送 `develop`。

## WEB-M2-02 实际检查

- 将原静态说明页替换为可导航的模块入口，入口只连本地草稿；提交、查询、审批、占用均说明真实服务依赖。更新模块 README，避免旧“只有说明页”描述过时。
- `npm --prefix apps/web run build`：PASS；`bash scripts/check.sh`：PASS（2 项现有 OpenAPI 操作、四服务健康、Python 编译、Vue 类型与生产构建）。草稿校验函数测试 5/5 PASS。
- `NODE_PATH=<Codex 捆绑 Node 模块> WEB_BROWSER_CHANNEL=msedge node apps/web/src/modules/m2/tests/home.browser.cjs http://127.0.0.1:4187`：本地生产预览 PASS，覆盖单标题、诚实的可用范围、草稿导航、320px 无横溢、焦点与无 API 请求；草稿浏览器回归也 PASS。首次测试在 Vue Router 导航完成前读 URL，测试等待导航后通过，产品代码无需变更。
- 当前未有业务 HTTP、DB/身份服务端联调或部署证据；本批提交、push 与团队评审仍待实际 Git/人类结果。
