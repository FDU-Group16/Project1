# M2 外部依赖登记

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
