# D-02 主数据服务

已实现房间和座位主数据；D-01 身份、D-03 通知、D-04 审计由后续责任组提供。D-02 的可用入口、测试及未验证范围见 [STATUS](STATUS.md)，API 字段与权限见 [契约](../../contracts/d-master-data.md)。

## 运行

先按仓库根说明准备 PostgreSQL 独立 `d` schema 与对应账号。设置 `D_DATABASE_URL`；服务启动时自动执行 `migrations/` 中尚未应用的版本。未配置数据库时健康检查仍可响应，业务请求为 503；健康检查不证明业务可用。

正式身份接入设置 `D_IDENTITY_URL` 为身份服务基址，当前消费假设调用 `/api/v1/auth/me`。服务间读取还需配置独立 `D_M1_TOKEN`，并在 M1 配置相同服务令牌。任何凭据均通过环境注入，勿提交到仓库。

```sh
uv run python -m services.d.seed
uv run uvicorn services.d.main:app --port 8004
```

种子仅创建 `demo-room-public`、`demo-room-cs`、`demo-room-ee` 和每室六座（`{roomId}-seat-01` 至 `-06`），均为合成资源；可重复，不覆盖管理员修改，也不恢复注销数据。种子独立于迁移，不自动在服务启动执行。

## 开发身份依赖

D-01 未交付时可显式配置 `APP_ENV=development` 和 `D_USE_DEV_IDENTITY=1`，然后使用四个合成 bearer：`dev-student-cs`、`dev-student-ee`、`dev-room-admin`、`dev-operator`。启动日志和 `X-Identity-Mode` 响应头均显示 `development-substitute`；这不是登录或真实认证。常规模式为 `real-http`，失败不会回退。清理清单见 [任务](tasks/2026-10-22-d02.md)。

## 验证

使用隔离测试库设置 `TEST_D_DATABASE_URL` 后运行：

```sh
uv run python -m unittest discover -s services/d/tests -v
```

测试写入临时房间并按 ID 清理；种子测试保留三间合成房间。不要对正式数据库运行测试。无测试 URL 时 PostgreSQL 行为测试明确跳过；身份适配测试使用本机 HTTP provider fixture，不能证明真实 D-01 可用。完整仓库检查为 `bash scripts/check.sh`。
