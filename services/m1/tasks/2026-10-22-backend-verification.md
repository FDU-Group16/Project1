# M1-01～08 后端实现与验收记录

日期：2026-10-22；实施范围/同步/用户授权见 [主任务](2026-10-22-completion.md)。本记录仅覆盖 m1 工作区中的后端与 M1 提供方契约，不表示部署、团队批准或 M2/M3/D-01/03/04 完成。

## 实现与验收

| 需求 | 源码 / 接口 | 验收证据 |
| --- | --- | --- |
| M1-01 | `dependencies.py`、`core.py`、`search.py`；可信身份适配、院系筛选和直接预约权限 | 不同院系结果与直接越权 API；缺失凭证、真实提供方故障和畸形身份失败关闭 |
| M1-02 | `search.py`；`GET /api/v1/seats` | 插座、停用座位/房间、开放日/时段、预约与多来源阻断过滤 |
| M1-03 | `reservations.py`；settings、create、cancel | 整点/未来/7天窗口/默认4小时可配置、幂等冲突、同座并发只有一个成功、跨座位用户重叠拒绝、半开边界、本人取消 |
| M1-04 | `checkin.py`；daily code、check-in | 房间/日期/HMAC、管理权限、缺少密钥503、本人范围、开始与+15分钟边界、无效Unicode输入422、幂等签到 |
| M1-05 | `scheduler.py`；独立进程、breaches/outbox | -15/+10/+15精确时钟、重复运行、停机补跑不补过期提醒、唯一违约、调度前过期预约不阻塞、失败重试、SIMULATED/ACCEPTED不声称DELIVERED |
| M1-06 | `history.py`；个人current/history/detail、rebook、breaches | 历史隔离；再次预约重新检查当前房间可用性、权限和冲突 |
| M1-07 | `operations.py`；运营事实统计 | 权限检查；预约/签到/取消/违约计数和裁剪小时数对账；无学生ID |
| M1-08 / X提供方 | `blocks.py`；M2/M3 PUT、provenance | M2重叠409、M3保留原预约、来源并集、同版本同请求重复响应、冲突请求/旧版本拒绝、释放墓碑、身份与路径匹配、M1/M2/M3来源查询 |

## 已执行验证

- `python -m compileall -q services/m1` 通过。
- 最终 `.venv/bin/python scripts/test-business.py` 使用新建、随机凭据的Docker PostgreSQL（未使用UI演示库），全部通过：D14项、M1 30项（25项真实PostgreSQL行为+5项无数据库适配边界，M1耗时16.104秒）。M1业务测试中D主数据为夹具，身份/通知为明确的开发适配；不能据此宣称真实身份/送达。
- 最终回归包含：在锁等待跨过签到截止后拒绝请求；用户已有重叠预约时不返回无法预约的其他座位；ACCEPTED仅写acknowledged_at、不写delivered_at；Unicode错误编码返回422。创建预约在锁后、D请求后读取时间；取消/签到在锁后重读，避免等待造成过期时间校验。
- `node scripts/check-contracts.mjs` 通过（D 11、M1公开13、M1内部2个操作及其本地引用）；`git diff --check`通过。
- 迁移001、002、003在上述新建空库自动重放；重复启动迁移未丢失结构。003增加SUPPRESSED状态和抑制时间。真实D-02↔M1网络集成同轮通过：CRUD、院系/本人范围、幂等、同座并发、多来源写回、schema权限隔离和D停机503。根仓库检查与前端验收由主任务记录。
- 测试从 `TEST_M1_DATABASE_URL` 获取显式可销毁数据库并仅清理M1表；未把健康冒烟、跳过的测试或提供方夹具当作业务联调证据。连接凭证未记录。

## 依赖、临时清单与后续集成

- D-02：实现只走 HTTP `/internal/v1/rooms` 和房间详情；契约 `d-master-data` v0.1.0（proposed）。上述真实网络验证已通过；主任务补充整体前端验收。M1不导入D业务代码、不读D schema。
- D-01/D-03/D-04：提供方未完成，本任务不实现。身份/通知/审计消费请求见 `contracts/d-dependencies.md` v0.1.0和 `contracts/m1-public.md`依赖章节。
- 完整临时清单：[TEMPORARY-DEPENDENCY inventory](../temporary_dependencies/README.md)。实际路径、开关、替换组、触发条件、应保留业务代码和检查均已列明。默认真实 HTTP，无隐式回退。开发标识同时出现在响应头、预约响应和调度输出。
- 提供方通知响应 accepted 仅记录ACCEPTED与acknowledged_at；DELIVERED才写delivered_at。D负责接收后的持久化投递、后续送达查询仍未集成。
- M2/M3应用的实际调用、审批/工单状态变化和补偿不在本任务内。网络写回提供方测试不等于真实业务链路演示。
- 后续由M1与D-01提出组M2、D-03/04提出组M3对齐批准契约并替换临时适配；M1与M2/M3完成真实状态写回联调。所有权、人工评审和部署均待团队登记。

发布字段：PR/提交由主任务按需求登记；当前记录不声明已提交。运行环境为本机测试；部署tag、发布、生产迁移、远端运行和人工验收未验证。

## 独立审计修复

- `masterdata.py`对D返回的完整RoomWithSeats做严格消费方校验：departmentId必须存在（允许null），布尔/小时/星期不做类型强转，验证开放边界、稳定ID/座位编号唯一、seat.roomId归属与请求roomId一致。畸形数据返回503，不会缺省当公共房间或误把字符串false当true。新字段可兼容忽略。
- `request_d`禁止所有HTTP重定向并关闭错误响应。真实本地双HTTP服务器测试301/302/303/307/308的GET/POST：目标端收到0次请求，未转发凭据。
- 发件箱投递前重新检查提醒的预约状态/时间；失败后已取消、已签到或过期的提醒转SUPPRESSED，NO_SHOW和审计保留。锁顺序为room/user→reservation→outbox，避免与业务事务逆序死锁；有界候选快照和SKIP LOCKED支持多worker。
- 新行为测试验证失败→取消、失败→签到、失败→过期均不再投递提醒，违约通知/审计仍保留正常投递路径。真实通知提供方仍未完成，SUPPRESSED仅为M1消费方行为证据。
