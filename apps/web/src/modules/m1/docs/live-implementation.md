# M1 实时页面实施记录

2026-10-22；当前 `m1` 工作树。任务范围：M1-01～M1-08 的 Web 消费页面。用户授权的业务默认值由父任务 ADR 记录；跨模块 develop 核验由父任务记录。公共修改责任与临时身份库存见 [身份消费记录](../../../shared/auth/docs/auth-integration.md)。

| 需求 | 实现文件/行为 |
| --- | --- |
| M1-01/02 | `pages/SeatSearchPage.vue` + `api.ts`；带插座筛选、整点时段查询、实时座位选择、院系范围由后端执行 |
| M1-03 | `search.ts` 的北京时间→UTC 转换、配置时长；预约确认使用幂等键，查询/条件变化清理旧结果；`pages/SettingsPage.vue` 可配置最大时长 |
| M1-04 | `components/CheckInForm.vue` Web 编码签到；`pages/RoomStatusPage.vue` 管理员当日编码展示；服务端校验 `[start,start+15min)` |
| M1-05 | `pages/BreachesPage.vue` 分页失约记录与关联预约；提醒/到期由后端调度，前端不假装通知已送达 |
| M1-06 | `pages/LiveReservationsPage.vue` 当前/历史分页、详情/取消；`components/RebookForm.vue` 同座位重新预约且重新校验 |
| M1-07 | `pages/OperationsPage.vue` 日期筛选、总计/房间/座位统计，不展示学生身份 |
| M1-08 | `pages/RoomStatusPage.vue` 分页 M1/M2/M3 来源记录；前端不调用内部写回接口 |

接口：[M1 public v0.1.0 proposed](../../../../../../contracts/m1-public.md)。此版本正在当前任务实现，仍需组内评审；真实 D 身份/通知/审计不在本次范围。固定展示示例仍独立保留在 `/m1/preview/*`，与实时页面数据和写操作隔离。

## 状态与验证

实时页面有加载、空态、失败、未登录与权限保护；表单支持键盘；布局沿用既有视觉风格，新增样式以 scoped 引用公共 feature 样式。用户可查询/重试，非幂等 D 创建失败需先核对列表；M1 预约和再预约在同一未确认尝试中重用幂等键。

- 2026-10-22 `npm --prefix apps/web run build` 和 `npm --prefix apps/web run typecheck` 通过；`git diff --check` 通过。
- 真实 IAB 已检查游客跳转、开发身份显式标识、服务不可用状态、桌面布局；M1 搜索与 D-02 新建表单在 320px 无横向溢出（scrollWidth=clientWidth=320），移动菜单 Escape 关闭并恢复焦点、学生→管理员切换后重新构建页面，浏览器运行错误为空。完整真实 HTTP 快乐路径及根检查由父任务验收记录补充，未完成前不作通过声明。
- 未部署。没有真实 D-01/D-03/D-04 联调证据；M2/M3 提供方端到端写回仍待各组接入。

下一步：父任务完成 PostgreSQL/HTTP 集成与浏览器验收，按需求分提交；受影响组评审后才能合并，真实身份可用后按库存替换开发依赖。
