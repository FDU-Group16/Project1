# M3 依赖接入与清理清单

当前登记为 [DEPENDENCIES.json](../DEPENDENCIES.json)，状态入口为 [STATUS.md](../STATUS.md)。本次基线为 `origin/develop@13dcd59f9a46c859f8593b530d7aa54c27faaf1f`，工作目录为 `工程伦理/develop/Project1`；原重建记录保留在 implementation.md，只表示旧工作区的历史证据。

| 依赖 / 提供方 | 当前消费者、契约与缺口 | 临时文件及配置 | 替换触发、验收与保留代码 |
| --- | --- | --- | --- |
| M3-D-DEV / D-01(M2)、D-02(M1) | `http_directory.py` 已实现真实用户身份与公开房间 HTTP 消费；D-02 已有提供实现，D-01 及维修人员目录仍缺。`contracts/m3-directory-dependencies.md@0.1.0` 为 proposed 消费假设，继承 d-dependencies/d-master-data 0.1.0。 | `services/m3/dev_dependencies.py`、`services/m3/seed.py`，`run-dev.sh` 中 `M3_MODE=development` 和 `M3_DIRECTORY_MODE=development`；合成房间、旧 demo token 及与共享开发会话对齐的 dev token。Web 已使用共享登录，不再在 M3 目录保存第二套会话；公共身份替身由其自身登记负责。 | M3、M2/D-01、M1/D-02 与公共 Web 负责人评审权限/范围/人员目录；真实 D-01 就绪后用正式用户验证会话失效、无权限、院系范围、人员撤权和目录故障，再清理上述开发路径。保留 Actor/Directory 接口、真实 HTTP 适配、服务端权限与长期失败测试；不能把开发 token 改名作为正式身份。 |
| M3-M1-DEV / M1-ROOM-BLOCKS(M1) | `m1_client.py`、worker/outbox 消费真实 M1 网络接口；`m1-room-blocks.openapi.json@0.2.0-proposed`，M1 与 D-02 已在本副本基线。联调任务进行中，源程序存在不等于已联合验收。 | `services/m3/dev_m1_stub.py`；`run-dev.sh` 默认 `M3_M1_MODE=development-http`、3113 地址、公开合成服务 token。替身仅做来源回执，不实现座位业务。 | 由 M3 与 M1 负责人验证真实 ACTIVE/RELEASED、精确回执、M3 独立服务凭据、重放、故障与多工单/M2/个人预约限制保留；真实 D-01 及正式环境最终验收后移除开发服务和启动分支。保留 M1 HTTP 客户端、严格校验、状态机、持久 outbox、SLA/租约/恢复测试。 |
| M3-D-DELIVERY / D-03、D-04（均归 M3 组） | `d-dependencies.md@0.1.0` proposed；两公共子域仍 `not_ready`。本次只适配工单，未实现通知/公共审计调用或投递替身。M3 的历史与管理员超时待办不是 D 通知或公共审计完成。 | 没有伪成功投递路径或开关，因此 `marker_paths=[]`；登记为未完成依赖。 | 单独明确两公共子域的接口、数据与交付范围后由 M3 组实施；消费者须真实验证幂等、拒绝/故障与送达/审计证据。保留 M3 当前历史与待办，它们是工单业务，不因公共服务落地删除。 |

正常生产仅 `M3_DIRECTORY_MODE=http`、真实 M1 HTTP、独立 PostgreSQL；缺配置不装配业务，远端失败不回退。所有临时实现仅 development/test 显式启用。`CONTRACT-ASSUMPTION M3-D-DEV` 在 `http_directory.py` 标注待提供方评审的长期消费者适配；它不是临时成功返回。Shell 启动文件属于清理清单，但当前登记扫描只检查 py/ts/js/vue，因此不写入 `marker_paths`。

`tests/integration_real_providers.py` 的身份 HTTP 夹具、其他 HTTP/目录注入夹具只用于可重复消费者测试，不能作为 D-01 已提供的证据。集成结果由独立 QA 写入当前记录；provider-ready 与 consumer-verified/cleaned 分开。尚无提交 SHA 与正式 D-01 联调，因此 `verification` 保留 null，不以本地夹具冒充完成清理。
