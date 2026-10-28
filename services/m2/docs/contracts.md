# M2 内部协议草案

版本：0.1.0-proposed；A主维护、B待评审。Actor、TimeRange、ApplicationCreate、请求摘要和A0-05同步Base/Session/UoW已上传；A1-01核心申请存储已上传；A1-02新增核心保存防重（见末节），本地待验收。以下业务DTO、枚举及Port仍为签名草案，不能宣称M2-BASE完成。同步技术范围已获用户确认；业务政策与团队接口评审仍未完成。

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

## 请求摘要与作用域实现（A0-04，本地待验收）

`services/m2/idempotency.py`实现不可变`IdempotencyScope(user_id, action, target, key)`；`storage_key`返回四元组，不拼接分隔符，不trim/casefold。标识值必须是非空字符串，键沿用公开契约minLength=1；可信user_id由未来身份适配器提供。动作和目标由路由/用例决定，不取浏览器自报值。创建申请的建议动作/目标为`create`和`/applications`，尚无注册路由。

`application_input_digest(ApplicationCreate)`重新校验JSON输入，对已规范化五字段按键排序、无额外空格、UTF-8序列化，以`m2.application-create.v1`加NUL作为域前缀计算SHA-256，返回`m2.application-create.v1:sha256:<hex>`。用途首尾空白和等价UTC小数秒表示被归一化；房间ID、用途内部空白和大小写保留。模型新增字段或规范化规则变化时，必须评估已存幂等记录兼容性并显式版本化，不能静默更改旧摘要。

该函数不读写幂等记录，不鉴权、不作业务冲突决定、无HTTP 409/202回放。后续数据库仍须联合唯一约束、业务意图和结果同事务、失败回滚；B提出的审批初始化可信快照及资源回执持久领取/终结入口仍待单独共同评审。本批不修改这些签名或批准政策。摘要不构成匿名化，不输出实际申请内容或摘要到公共日志。


## A0-05 已落实的事务接口（2026-10-27，本地已验证，待验收上传）

用户确认同步风格，本批唯一实现为 `services.m2.db.Base`、`create_m2_engine(url)`、`create_session_factory(engine)` 与 `services.m2.uow.M2UnitOfWork(factory)`。其他 Port/业务 DTO 保持上述 proposed；公开 HTTP 契约版本不变。依赖尚未由 B 或全组维护者评审。

UoW 遵循既有显式 commit 约定：enter 开启一次事务，session 属性只在活跃且未终结阶段可用；顶层 commit 后结束事务，异常/遗漏 commit 的退出回滚，最后永久关闭 Session；显式 rollback 同样终结本次事务。提交失败先 rollback 并继续抛出故障。每个 UoW 单次使用，禁止嵌套/复用，ports 只可使用/flush 共享 session。成功 commit 后发生的异常不能回滚已提交结果，因此顶层应把 commit 放在最后一步。网络 I/O 在事务外。

M2 metadata 默认 schema=m2；连接工厂不联网、不加载 .env。Alembic head 为 `0001_m2_schema`，版本表限定 m2，未含申请表；B 后续模型必须继承同一 Base、迁移衔接唯一 parent。真实事务与迁移验证结果见 A0-05，不能以可导入替代数据库通过。


## A1-01 核心申请存储（2026-10-27，本地待验收）

唯一主表模型`services.m2.models.Application`使用既有Base；新增迁移0002_applications，无第二Base/迁移链。保存application_id(UUID)、applicant_id/applicant_department_id/room_id(不透明Text)、start_at/end_at/created_at(timestamptz)、purpose、attendee_count。主键防重复ID；非空、正人数、用途长度、时序约束是输入结构约束。未设置默认业务状态/截止或审批层级，不改变公开协议。

内部存储`services.m2.applications.ApplicationStore`：

```python
insert(*, uow, application_id: UUID, actor: Actor, data: ApplicationCreate, now: datetime) -> ApplicationData
get_mine(*, uow, application_id: UUID, actor: Actor) -> ApplicationData | None
list_mine(*, uow, actor: Actor, page: int = 1, page_size: int = 20) -> ApplicationPage
```

insert重验输入、要求非空可信院系及带时区时钟，仅flush；重复UUID由数据库报错并由UoW整体回滚，不当作幂等键回放。ApplicationData为不可变核心数据快照，ApplicationPage.items为tuple；它们不是公开ApplicationView。get_mine/list_mine始终按Actor.user_id过滤，不接受浏览器另传owner；未知/他人ID同为None。分页正整数、每页1–100，created_at/UUID倒序，单SQL快照计算本人total和页面，空页保留total。

该仓储不是完整ApplicationPort，不包含transition或审批人查询；不得直接暴露为提交/详情HTTP。后续顶层必须真实认证、资格/房间校验，再补经评审的状态/version/路由/截止字段、幂等和真实审批初始化；这些写入共享一个UoW。B初始化可信快照、回执持久恢复建议仍待独立共同接口批次。


## A1-02 核心创建防重（2026-10-28，本地待验收）

内部入口`application_creation.ApplicationCreationStore.save(*, uow, actor: Actor, data: ApplicationCreate, key: str, now: datetime) -> ApplicationSaveResult`。
结果不可变：`application: ApplicationData`、`replayed: bool`。同作用域不同输入抛`ApplicationCreationConflict`（错误消息不含键/申请内容）。
作用域user_id由Actor提供，action固定core-create-v1、target固定/applications/core，key保持原义；复用A0-04的规范化摘要版本，不改其编码。

每次调用前顶层须重新验证身份/权限；数据层不构造身份，不缓存授权，不接受浏览器指定owner。回放仍用get_mine校验实际归属，坏关联显式失败而不泄露其他申请。
模型`ApplicationCreationKey`与`Application`共用唯一Base；四字段联合PK、application_id唯一且FK指向现有主表、非空/摘要格式/内部作用域约束。无TTL、覆盖或删除入口。

READ COMMITTED下先查键，新键在SAVEPOINT写候选申请+ON CONFLICT DO NOTHING键；重复候选仅SAVEPOINT rollback，然后新语句读取已提交赢家。父UoW仍由顶层commit/rollback，数据库故障不吞，其他隔离级别拒绝。SAVEPOINT释放不是业务commit；后续用例失败整体回滚申请和键。并发赢家回滚时另一请求可成为创建者。

公开OpenAPI仍0.1.0-proposed，未注册新HTTP。该表不是所有公开写操作的统一幂等状态机，没有operation_id/202/终结响应快照。未来正式提交须另定公共幂等作用域/结果生命周期、经确认的工作流和真实B.initialize同事务；不能把本批核心保存记录回放成“已提交申请”。
唯一head0003_creation_keys，parent0002_applications；B需要评审后在实际接入head接续迁移，不另建申请表。无新依赖、公共配置、B实现或跨模块调用。边界与68测试证据见[A1-02](tasks/A1-02.md)。
