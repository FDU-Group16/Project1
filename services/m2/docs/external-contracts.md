# M2 外部依赖登记

## 最新核对：2026-10-30

依据本轮成功fetch的 origin/m2@f720bea5319b9273e88db22f93d53eadecc5f9b1、origin/develop@50ccf95f1fda292c907a3d1907f1c99f5b99f012。A已安全快进m2；develop与m2有26/12个独有提交，仅读取该SHA，未合并/部署/真实联调。具体范围见[A1-03](tasks/A1-03.md)。

| 依赖 | 最新可核对事实 | 对M2的影响与下一步 |
| --- | --- | --- |
| D身份/RBAC | develop的contracts/d-dependencies.md为0.1.0-proposed，提出Bearer GET /api/v1/auth/me及id/departmentId/permissions。services/d/STATUS.md仍将正式D-01标未实现/not_ready；临时test_accounts为显式staging/test合成账号，departmentId=null且无m2.apply/审批管理范围 | 不能直接构造合格申请人或将临时登录等同正式鉴权。需M2/D负责人明确权限名、可信院系/管理范围与真实身份接口。该远端记录确定M2组负责D-01，不等于本聊天已获整套D实现任务 |
| D房间 | develop的d-master-data.md/OpenAPI 0.1.0-proposed已实现，字段id/name/departmentId/openHour/closeHour/weekdays/active/retired，另有座位；内部读当前使用M1专用D_M1_TOKEN | 不能借用M1凭据。M2需评审容量含义、审批路由、读取授权与开放时间语义；不把座位数自动当批准的整室容量 |
| M1 | develop含真实业务及room-blocks 0.2.0-proposed；本地m2仍为0.1.0-proposed契约，无M2真实消费实现 | 提供方已存在与M2已接入分开；先核对协议差异/受影响组评审，再在获准集成任务中接入，不能复制提供方代码或假报G5通过 |
| 公共Web | develop已有共享认证、HTTP与代理代码；本地m2尚未集成。m2已有/m2入口和/m2/apply本地草稿，两个前端提交均已上传 | 无需重建页面或共享客户端。正式API接入需人工处理分叉并验证兼容性；草稿仍无保存/提交请求 |
| B初始化 | m2最新可见B交接为10月26日接口评审，ApprovalPort可信快照/持久恢复建议尚待共同评审 | 不能称申请与首级待办已原子创建；继续等待真实初始化或另列显式隔离测试任务 |

正常身份失败应区分401/403/503，不回退假身份。D-02及临时身份在提供方交接中的测试是提供方证据，本轮没有复跑其数据库、创建账号或连接业务服务。正式申请政策、共享接口审批与部署验收仍须单独确认；没有自动处理分叉或扩大A范围。

下一真实集成任务需明确：由人整合两个分支并保留双方实现/锁文件/部署配置；评审M2身份与房间字段；落实B初始化与事务；再接公开HTTP和现有草稿。A1-03仅修复独立输入边界，不跨过这些依赖。

## 以下为2026-10-22历史快照

日期：2026-10-22。来源：origin/develop@99ce858a2bbf8caa2f4b226a83f989c54d6992d1，以及GitHub分支/PR只读查询；本地已检出同一代码。未发现A/B远端个人分支或M2业务PR；无法据此推断队友本地是否已开发。

| ID/提供方 | 协议与能力事实 | 认证、地址与重试 | 后续验收/责任 |
| --- | --- | --- | --- |
| M2-DEP-M1 / M1 | contracts/m1-room-blocks.openapi.json@0.1.0-proposed；PUT /internal/v1/room-blocks/m2/{sourceId}未实现 | 服务Bearer签发未定；后端M1_BASE_URL待配置，绝不复用用户令牌；相同PUT/revision/载荷重放，无GET lookup | A消费、B编排、M1提供；真实占用/来源释放/迟到墓碑/冲突 G5 BLOCKED |
| M2-DEP-D-IDENTITY / D | 身份、权限、管理范围及服务身份未定稿/未实现 | 认证载体、签发/验证和配置名待D；不相信浏览器自报权限 | D负责人待定；A适配，B消费可信Actor，真实鉴权BLOCKED |
| M2-DEP-D-ROOM / D | 稳定ID、容量、开放范围、院系和路由未定稿/未实现 | 网络查询URL/认证/错误策略待契约，不直读D表 | D主数据负责人待定；A消费，真实资格验证BLOCKED |
| M2-DEP-D-EVENTS / D | 通知、审计契约未定稿/未实现 | 事件幂等、重试、送达口径待定 | B业务触发/worker，D提供；未送达不标成功 |
| M2-DEP-WEB / 公共Web | shared/api和auth仅README，登录入口是静态页面；未有API代理 | /api/m2保留前缀方案待确认，页面不硬编码服务地址 | 公共维护者提供，A/B模块接入，BLOCKED |
| M2-DEP-CI / CI | check.sh仅M1静态契约+四服务健康+Vue构建；CI push仅main/m1/m2/m3 | feat个人push未覆盖；PR触发；develop另有部署 | E-03限定共享任务，维护者待定 |

## M1 兼容性重点

仅发送roomId/revision/status/startsAt/endsAt五字段。sourceId保持application_id；revision与申请version分开。200还需逐字段匹配及UTC校验，不能200即成功。分别识别ROOM_OCCUPANCY_CONFLICT、STALE_REVISION、REVISION_PAYLOAD_MISMATCH；未知409不可当占用冲突。超时/断连/503或无效200结果为未知；原命令持久重放。确定不可重试错误保留需人工处理状态。

M1响应endsAt在通用schema可选，而M2有限时段确认需要返回；DEC-09待双方确认，不能宣称提供方保证。释放先到/后到均须墓碑防旧ACTIVE；真实联调必须验证不释放M3/其他申请来源。

## 模拟、实现与部署边界

本批无临时替身、无真实业务HTTP调用、无凭证、无数据库或worker。消费者适配也尚未实现。所有真实集成保持BLOCKED。后续每项替身须在对应任务登记TEMPORARY-DEPENDENCY及精确清理清单；本登记不是替身已实现或删除授权。
