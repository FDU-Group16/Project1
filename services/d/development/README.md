# TEMPORARY-DEPENDENCY D02-IDENTITY

Minimal synthetic identity fixture for D-02 acceptance while D-01 is unavailable. Enable only with both `APP_ENV=development` (or `test`) and `D_USE_DEV_IDENTITY=1`. No login/account management, session lifecycle or real student data exists here. Unknown bearer values return 401. Production environments reject activation. Real-service failure never selects this fixture.

Removal inventory, ownership and integration trigger: [D-02 task](../tasks/2026-10-22-d02.md). Preserve D-02 business logic and real HTTP identity adapter during replacement.
