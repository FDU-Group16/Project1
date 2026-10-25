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

## A0-03：本地申请输入校验（待验收）

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
