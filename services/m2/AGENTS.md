# M2 局部协作规则

本文件补充根 AGENTS.md；A 主维护，B 待评审。角色入口为各自 docs/automation/ROLE_A.md 或 ROLE_B.md，缺失时不代写另一角色任务书。

- 真实状态读取 STATUS.md、docs/baseline.md、docs/contracts.md、docs/external-contracts.md 和本角色 progress。proposed 不能当成批准或实现。
- A 维护申请、资源客户端/命令仓储、共同定义与正式装配；B 维护审批、超时、恢复编排与 worker。共同协议仅一份，B不另建 Base/申请主表/数据库工厂。
- 新批次先用根任务模板记录精确文件、需求与验收；共享依赖、流水线、代理、schema等先落具体共享任务。只在本角色专用checkout及个人分支写入。
- 写入/安装/生成之前检查实际路径、origin、HEAD、全部暂存/未暂存/未跟踪改动和未完成Git操作；原子创建实际git目录下 m2-a-run.lock 或 m2-b-run.lock，记录运行ID和活跃进程。已有未知锁不删除。每个checkout只允许一个写入者；锁必须跨安装、编辑、验证持有，完成只释放自己的锁。
- 顶层用例拥有事务；port共用传入UoW，不独立commit。网络请求在事务外；正式装配只注册真实可用实现，不回退假身份/假审批/假M1成功。
- 测试、迁移、worker核实隔离资源；未知目标不连接。测试替身遵循根规则登记与清理，不把替身通过写为真实集成通过。
- 每批展示完整tracked及untracked差异与测试，达到READY_FOR_REVIEW后等待本人验收；未验收不提交。上传遵循角色任务书第6/7节的精确个人分支、内容核对与Asia/Shanghai 09:00–18:00窗口。
- 本轮仅A0-01接口准备。数据库、业务状态机、HTTP处理器、B代码和部署均尚未实现。
