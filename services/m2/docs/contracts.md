# M2 内部协议草案

版本：0.1.0-proposed，2026-10-22；A主维护、B待评审。A0-02 已在 `services/m2/contracts.py` 实现 Actor 和 TimeRange；A0-03本地新增ApplicationCreate（尚待验收），其余DTO、枚举及以下Port仍为签名草案，无数据库或可调用port实现，不能宣称M2-BASE完成。拟选同步接口，DEC-07若选择异步须整体修订。

公开JSON类型、字段/错误/鉴权/分页见 [M2 OpenAPI](../../../contracts/m2.openapi.json)。当前只作结构检查；JSON合法不意味着业务API可用。

## 共同类型与时间

唯一代码入口为 services/m2/contracts.py，使用Python标准库及工程已锁定的Pydantic，不导入审批/申请用例。Actor字段已落实；TimeRange为新增内部值对象，接受两个带时区datetime、归一UTC并拒绝空/反向区间，overlaps按半开区间比较，不判断房间是否可用。Actor构造只校验数据形状，不认证用户、不授予权限；集合在构造时冻结，外部ID保持原义，必须由可信适配器提供。其余类型以下仍是实现目标。DTO取公开契约中的ApplicationCreate、ApplicationView、TaskView、ApprovalRecordView、ApprovalProgress、OperationPendingResponse和状态枚举。

- Actor：user_id: str；permission_codes: frozenset[str]；department_id: str | None；managed_department_ids/managed_room_ids: frozenset[str]；manage_all_departments/manage_all_rooms: bool = False。必须来自可信身份适配器，空集合不等于所有范围。
- ManagedScope：kind为DEPARTMENT/ROOM；scope_id不透明字符串。申请保存已验证院系及路由快照，缺路由不能产生无人审批的申请。
- M2内部ID为UUID字符串；外部ID保持原义。内部datetime全部带时区，UTC序列化Z；区间[start,end)。不接受无时区输入。
- ApplicationStatus：PENDING_LEVEL_1、PENDING_LEVEL_2、RESOURCE_PENDING、APPROVED、REJECTED、WITHDRAWN、EXPIRED。TaskStatus：PENDING、PASSED、REJECTED、CLOSED。
- BlockStatus：ACTIVE/RELEASED；ResumeTarget：PENDING_LEVEL_2/EXPIRED。申请version与M1 revision独立。
- RoomBlockCommand（不可变业务载荷）：command_id/application_id/operation_id: str；revision: int；desired_status: BlockStatus；room_id: str；starts_at/ends_at/created_at: datetime；correlation_id/request_digest: str。HTTP只发送五字段；operation_id等关联字段不外传。
- RoomBlockResult：kind为APPLIED/OCCUPANCY_CONFLICT/STALE_REVISION/PAYLOAD_MISMATCH/UNAVAILABLE_OR_UNKNOWN/NONRETRYABLE；applied_state为经完整校验的M1回执或None；safe_error_code/safe_message为str或None。APPLIED必须有匹配回执，错误不能携带凭证。
- ResourceLease：command: RoomBlockCommand；lease_token: str（每次claim重新生成，不能仅worker_id）；worker_id: str；leased_until: datetime；attempt: int。resume_target为独立持久化元数据，不能塞入不可变请求摘要。
- CommandReceipt：command_id、lease_token、result、received_at、next_retry_at（datetime或None）。持久记录诊断与重试时间；业务状态终结由B编排。

## 用例/Port签名（评审后落实到唯一代码文件）

```python
class M2UnitOfWork(Protocol):
    session: Session  # 拟议SQLAlchemy Session；只在M2内共享
    def __enter__(self) -> "M2UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

class ApprovalPort(Protocol):
    def initialize(self, *, uow: M2UnitOfWork,
                   application: ApplicationView) -> None: ...
    def close_pending(self, *, uow: M2UnitOfWork, application_id: str,
                      reason: str, now: datetime) -> None: ...
    def progress(self, *, uow: M2UnitOfWork, application_id: str,
                 actor: Actor) -> ApprovalProgress: ...

class ApplicationPort(Protocol):
    def get(self, *, uow: M2UnitOfWork,
            application_id: str) -> ApplicationView: ...
    def transition(self, *, uow: M2UnitOfWork, application_id: str,
                   expected_version: int, expected_status: ApplicationStatus,
                   target_status: ApplicationStatus, current_step: int | None,
                   reason: str | None, now: datetime) -> ApplicationView: ...

class RoomBlockPort(Protocol):
    def put_state(self, *, command: RoomBlockCommand) -> RoomBlockResult: ...

class ResourceCommandStore(Protocol):
    def new_target(self, *, uow: M2UnitOfWork, application: ApplicationView,
                   desired_status: BlockStatus, operation_id: str,
                   resume_target: ResumeTarget | None) -> RoomBlockCommand: ...
    def latest(self, *, uow: M2UnitOfWork,
               application_id: str) -> RoomBlockCommand | None: ...
    def claim(self, *, uow: M2UnitOfWork, worker_id: str, now: datetime,
              lease_seconds: int, limit: int) -> list[ResourceLease]: ...
    def renew(self, *, uow: M2UnitOfWork, command_id: str, lease_token: str,
              now: datetime, lease_seconds: int) -> ResourceLease | None: ...
    def is_current(self, *, uow: M2UnitOfWork, command_id: str,
                   lease_token: str, now: datetime) -> bool: ...
    def save_result(self, *, uow: M2UnitOfWork,
                    receipt: CommandReceipt) -> bool: ...
    def schedule_retry(self, *, uow: M2UnitOfWork, command_id: str,
                       lease_token: str, now: datetime,
                       next_retry_at: datetime, safe_error_code: str) -> bool: ...
    def promote_resume_target(self, *, uow: M2UnitOfWork,
                              application_id: str, command_id: str,
                              expected_version: int, now: datetime) -> RoomBlockCommand: ...
```

## 事务、并发与错误约定

- A提供工厂、Base、ApplicationPort、命令仓储；B实现ApprovalPort和审批编排/worker。顶层用例创建UoW并commit；port不commit/rollback，可flush；未提交或异常退出回滚并关闭Session。跨服务不共享数据库、Session或ORM模型。
- A创建申请、B.initialize、公开幂等结果共用同一短事务。initialize重复安全，唯一一级待办。撤回/驳回/过期与close_pending同事务；失败整体回滚。ApprovalPort.progress自行核对Actor的读取权限，ApplicationPort.get是仅供已授权顶层用例使用的内部读取，不直接映射公开接口。
- transition执行合法迁移及expected_version/expected_status条件更新；不允许任意覆盖终态。顶层仍承担可信身份、范围、禁止自批与新鲜时钟检查。正式状态表须经DEC-02～06确认，不能仅靠这份文档投入生产。
- new_target在锁定/条件更新申请的事务中分配持久revision。相同operation_id+目标返回原命令；参数不同必须冲突，不静默覆盖。重试不调用new_target。新RELEASED替代ACTIVE后停止调度旧ACTIVE。
- claim只领取到期、未被替代、非终结且租约可取得的命令；分配新lease_token和递增attempt。renew拒绝过期、被替代或旧token。数据库选择SKIP LOCKED/条件更新等方案待G2真实PostgreSQL验证。
- 每次发送前短事务is_current，关闭事务后网络PUT；实际网络在途仍可能竞争，M1版本墓碑才是最终防线，租约不能代替来源版本。
- save_result只允许当前命令、当前未过期租约的回执，依据receipt.received_at核对租约；返回False表示迟到/替代，禁止修改申请或终结原操作。成功持久化回执可由B在同事务读取并编排状态/唯一审批记录/原幂等终结。调度状态必须能区分“已收到结果但未完成编排”，保证进程崩溃后不会丢失恢复入口；下一实现批次明确持久字段与领取规则。
- schedule_retry只更新当前有效lease的原命令，next_retry_at必须晚于now；释放领取资格、保存有界退避。确定不可重试错误改需处理状态，保留恢复入口；B决定策略，A仓储不启动循环。save_result若同时给next_retry_at则与该方法遵循同一约束，不能重复增加attempt。
- promote_resume_target只允许当前RELEASED对应申请处于RESOURCE_PENDING且version匹配时将恢复目标提升到EXPIRED；同目标重复安全，不改HTTP载荷/revision，不允许降回二级待审。具体锁/条件失败映射为内部并发冲突。
- 拟议内部错误：ApplicationNotFound、ConcurrentModification、InvalidTransition、CommandConflict、LeaseLost、DependencyUnavailable。正式公共error.code的完整枚举在实现批次结合共享错误契约评审；不可泄露SQL或凭证。布尔False仅表示租约/时效冲突，不吞数据库故障。

## B的持久化意图与组合验收

B在进入RESOURCE_PENDING的事务持久化ApprovalAttempt：operation_id、application_id、task_id、原actor_id/comment、规范化摘要、请求时间、原expected_version、ACTIVE命令ID、公开幂等关联。恢复仍记原审批人，worker执行者另作审计。当前ACTIVE回执匹配且新事务now<deadline才APPROVED；否则更高RELEASED清理。资源冲突清理后回二级待审，原operation结束为RESOURCE_CONFLICT；过期则终结为过期失败，不能一直202。

B需评审：上述签名、租约过期回执处理、结果落盘与编排崩溃恢复、关闭失败原子回滚、唯一审批意图/记录、迁移parent。本批不创建B文件或宣称B接受。

后续G2/G3/G4至少验证：initialize/close_pending抛错无部分提交；并发同键仅一申请/待办；两领取者不共享有效lease，旧token不能写回；M1已应用但本地失败可原PUT恢复；释放先到、迟到ACTIVE、到截止只提升恢复目标不重复增加revision。外部服务替身只能验证M2内部行为，G5需真实服务证据。

## ApplicationCreate 本地实现边界（A0-03）

按公开OpenAPI现有五字段校验，多余字段一律拒绝，不能传入申请人/院系/审批状态。用途修剪后检查长度，人数严格正整数，外部room_id只检查非空字符串并保留原义。公开时间只接受UTC Z字符串并校验真实日期及时序；内部TimeRange仍可接受其他带时区datetime。通过校验仅表示输入结构可用，不表示房间存在/开放、身份可信或业务申请成功。未注册路由，未更改proposed状态；ApplicationView和业务Port仍未实现。
