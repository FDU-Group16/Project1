# TEMPORARY-DEPENDENCY D02-IDENTITY

[DEPENDENCIES.json](../DEPENDENCIES.json) 登记本依赖，提供方状态见 [PROVIDES.json](../PROVIDES.json)。M2 可运行 `python3 scripts/check-dependencies.py --provider D-01` 发现仍待接入的 D-02；真实联调与清理后由 M1 更新消费记录，步骤见[交接指南](../../../docs/temporary-dependency-handoff.md)。

Minimal synthetic identity fixture for D-02 acceptance while D-01 is unavailable. Enable only with both `APP_ENV=development` (or `test`) and `D_USE_DEV_IDENTITY=1`. No login/account management, session lifecycle or real student data exists here. Unknown bearer values return 401. Production environments reject activation. Real-service failure never selects this fixture.

Removal inventory, ownership and integration trigger: [D-02 task](../tasks/2026-10-22-d02.md). Preserve D-02 business logic and real HTTP identity adapter during replacement.

D-01 归 M2，M1 维护 D-02 的这份临时消费替身。M1/M2 可在集成任务中协调修改或替换 `identity.py`、`dependencies.py` 的开发分支及开关；真实身份联调通过后按任务清单清理。`CONTRACT-ASSUMPTION D02-IDENTITY` 标出的真实客户端只允许按契约协调接口映射，保留主数据业务、真实请求、身份/权限校验及错误处理。注释更新见[本次任务](../../m1/tasks/2026-10-27-temporary-interface-comments.md)。
