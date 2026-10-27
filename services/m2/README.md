# M2 开发入口

当前仅 `services.m2.main:app` 的健康检查可用。A0-01新增规范草案；A0-02新增可导入的Actor和TimeRange及14项行为测试。申请、审批、数据库、迁移和worker尚未实现。

先读根与本模块AGENTS、[基线](docs/baseline.md)、[内部协议](docs/contracts.md)、[依赖](docs/external-contracts.md)、[A进度](docs/progress/A.md)。公开契约为 [M2 OpenAPI](../../contracts/m2.openapi.json) 0.1.0-proposed，不是运行时路由。

## 本机已验证工具与命令

项目要求Python 3.12；CI基线Node 24、uv 0.10.0。首次运行记录见A progress；机器绝对路径及本进程PATH存于本checkout的`.git/m2-a/runtime.json`和`runtime.sh`，不入库。定时运行重新核对工具，不依赖终端激活状态。其他电脑需自行配置兼容工具，不复制别人的绝对路径。

在通过任务书3.4保护检查并取得自己的checkout锁后，进入仓库根目录：

```bash
# 仅适用于本机已记录的A环境；其他电脑先配置自己的路径。
source .git/m2-a/runtime.sh
uv sync --frozen
npm --prefix apps/web ci
bash scripts/check.sh
```

2026-10-22已用上述锁定安装和check.sh验证骨架。检查脚本启动127.0.0.1:3911—3914的四个健康服务并停止本轮进程；先检查端口占用，不停止他人进程。此时代码未有数据库/外部业务调用。脚本只校验M1契约，M2静态草案需另行验证，尚未接入共享CI。

```bash
# 检查本批M2草案结构，不启动业务服务。
uv run --frozen python -c 'import json; from fastapi.openapi.models import OpenAPI; OpenAPI.model_validate(json.load(open("contracts/m2.openapi.json"))); print("M2 OpenAPI structure: PASS")'
```

`uv run --frozen uvicorn services.m2.main:app --host 127.0.0.1 --port 3102`是原有健康服务启动方式，只有确认端口空闲才运行；本批未单独验证3102，check.sh使用3912。

pytest/Alembic/worker命令尚未落地，不预写可用；后续任务先确认DEC-07与隔离测试数据库，再给经过实测的命令。查看完整验证边界与待决项：[A0-01任务](docs/tasks/A0-01.md)。

## A0-02：共同数据基础的操作验收

在仓库根目录使用Python 3.12运行（已配置项目环境时可用`.venv/bin/python`）：

```bash
python -m unittest discover -s services/m2/tests -p 'test_*.py' -v
```

A0-02时为14项测试；包含下方A0-03后应看到25项全部通过。测试直接导入`services.m2.contracts.Actor/TimeRange`；同一时刻的不同UTC偏移归一化一致，相邻时段不重叠，无时区/反向时间被拒绝，权限集合不会随调用方集合变化。Actor不验证身份；TimeRange不查询房间占用。通过这些测试不等于申请已落库或审批可用。没有测试替身、数据库或新依赖；共享CI暂未运行该单测命令。

设计及完整边界见 [A0-02任务](docs/tasks/A0-02.md)。后续B可复用已实现的两个值对象，其余Port/Base/UoW仍不能导入或宣称就绪。

## A0-03：本地申请输入校验（2026-10-25已上传m2）

代码在`contracts.py`的ApplicationCreate；只做输入验证，不代表申请已提交。使用现有项目环境，在仓库根目录运行：

```bash
.venv/bin/python - <<'PYCODE'
from pydantic import ValidationError
from services.m2.contracts import ApplicationCreate
payload = dict(room_id="demo-room", start_at="2026-10-29T02:00:00Z",
               end_at="2026-10-29T03:00:00Z", purpose="  课程讨论  ", attendee_count=6)
print("本地校验通过，未保存：", ApplicationCreate.model_validate(payload).model_dump_json())
try:
    ApplicationCreate.model_validate(payload | {"applicant_id": "forged"})
except ValidationError as exc:
    print("额外身份字段被拒绝：", exc.errors()[0]["type"])
PYCODE
```

预期：第一行用途变为“课程讨论”，第二行出现`extra_forbidden`。这些是合成输入，未连接身份、房间服务或数据库。`python -m unittest discover -s services/m2/tests -p 'test_*.py' -v`目前共25项测试；共享CI未接入该命令。任务与完整边界见[A0-03](docs/tasks/A0-03.md)。

## A0-04：申请重试识别基础（本地待验收）

`idempotency.py`提供作用域和输入摘要；数据库唯一约束及回放尚未实现。以下演示只比较合成输入，不保存申请：

```bash
.venv/bin/python - <<'PYCODE'
from services.m2.contracts import ApplicationCreate
from services.m2.idempotency import IdempotencyScope, application_input_digest
payload = dict(room_id="demo-room", start_at="2026-10-29T02:00:00Z",
               end_at="2026-10-29T03:00:00Z", purpose="课程讨论", attendee_count=6)
def digest(data):
    return application_input_digest(ApplicationCreate.model_validate(data))
print("相同内容重试：", digest(payload) == digest(payload | {"purpose": "  课程讨论  "}))
print("人数改变被识别：", digest(payload) != digest(payload | {"attendee_count": 7}))
a = IdempotencyScope("demo-user-a", "create", "/applications", "demo-key")
b = IdempotencyScope("demo-user-b", "create", "/applications", "demo-key")
print("不同用户作用域隔离：", a.storage_key != b.storage_key)
print("仅本地比较；未保存申请、未鉴权、未回放HTTP结果")
PYCODE
```

预期前三行均为True。当前M2单测共35项，命令仍为`python -m unittest discover -s services/m2/tests -p 'test_*.py' -v`。精确范围和验收见[A0-04任务](docs/tasks/A0-04.md)。摘要不是授权凭据；未来必须先鉴权再查幂等记录，作用域四字段须在业务事务内受数据库联合唯一约束保护。


## A0-05 数据库基础（2026-10-27，本地已验证，待验收上传）

技术选择已获本聊天用户确认：同步 SQLAlchemy 2.x + psycopg 3 binary + Alembic 1.x，依赖在根 pyproject.toml/uv.lock。安装使用 `uv sync --frozen`。不要再创建另一套 Base/Session 或迁移链。

```python
from services.m2.db import create_m2_engine, create_session_factory, database_url_from_env
from services.m2.uow import M2UnitOfWork

engine = create_m2_engine(database_url_from_env())
factory = create_session_factory(engine)
try:
    with M2UnitOfWork(factory) as uow:
        # 未来申请仓储和 B port 共用 uow.session，可 flush，不独立 commit。
        # 在这里调用实际实现；当前尚无申请/审批仓储。
        uow.commit()
finally:
    engine.dispose()
```

`M2_DATABASE_URL` 必须显式配置 `postgresql+psycopg`、主机、端口、库和账号密码；不读取通用 DATABASE_URL 或自动加载 .env。凭据只放忽略配置/秘密管理，勿写到终端历史或提交。引擎创建和模块导入不连接，首次用例才获取连接。UoW 显式提交；无 commit、异常或提交失败回滚。每个实例仅能使用一次，结束后禁止继续访问；已经成功 commit 的事务不能被之后的异常撤销。

迁移（事先人工核对目标；以下命令会写指定数据库）：

```sh
uv run --frozen python -m alembic -c services/m2/alembic.ini upgrade head
uv run --frozen python -m alembic -c services/m2/alembic.ini current
```

唯一 head 为 `0001_m2_schema`。schema 与版本表都在 m2；env 在同一事务先创建 namespace，revision 建立技术基点，不创建任何申请/审批表。禁止 Base.metadata.create_all 替代迁移。downgrade 到 base 保留 namespace/空版本表，不使用 CASCADE 删除未知表。未来 B 迁移须从此 head 协调接续；autogenerate 只检查 m2 namespace，生成结果仍需人工检查。

无数据库的普通检查：`uv run --frozen python -m unittest discover -s services/m2/tests -v`。没有专用测试环境时 PostgreSQL 类会明确 SKIP/NOT_RUN，这不证明数据库通过。

完整数据库验证需独立 PostgreSQL 18、回环 TCP、m2_a_test 库及同名非超级用户；从忽略配置设置 `M2_TEST_DATABASE_URL`、`M2_TEST_DATABASE_PORT` 和 `M2_TEST_DATABASE_CONFIRM=m2_a_test` 后执行同一命令。URL 禁止 query 参数，避免 host/service 重定向；测试先查询实际数据库/用户/地址/端口/权限/版本，再迁移和创建本轮随机探针表，结束只删除该表。角色不能有 SUPERUSER/CREATEDB/CREATEROLE。不要用共享库冒充这个目标，也不把这些约束视作通用生产配置。

本机私有集群与复现配置位于 A 忽略的运行目录，机器路径详见个人 progress。本批已在 PostgreSQL 18.6 验证空库迁移、事务和隔离检查，48 项测试全部通过（8 项真实 PG、无跳过），回滚故障注入有效，测试服务已停止。申请保存查询、HTTP、B 审批、M1/D 集成和部署尚未实现。详情见 [A0-05](docs/tasks/A0-05.md)。
