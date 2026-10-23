# M2 开发入口

当前仅 `services.m2.main:app` 的健康检查可用。A0-01新增规范草案；申请、审批、数据库、迁移和worker尚未实现。

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
