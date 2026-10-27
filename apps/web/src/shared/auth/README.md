# 公共登录状态

公共会话负责登录/me/logout 消费、sessionStorage 恢复、过期/退出清理与权限展示；M1、D-02、M3 使用同一入口，业务后端仍独立授权。D-01 提供方尚未实现，正式联调待其就绪。

课程测试站可由 D 服务显式启用[临时密码账号](../../../../../contracts/test-accounts.md)。登录页读取可选 `/auth/context`，仅精确匹配 `mode: test-accounts` 时展示公开用户名及测试说明；不展示密码，不构造会话，未知/404 不阻止原有密码表单。身份响应 `testAccount: true` 时公共布局持续提示测试身份；刷新和退出仍调用真实 `/me`、`/logout`。这与本机合成开发 token 分开，不代表正式校园 D-01 已完成。

M3 develop 适配通过公共请求客户端调用 `/api/m3/v1`，不建立第二套 token 或登录控件。公共开发身份仅在显式 `VITE_USE_DEV_IDENTITY=true` 且开发服务器下启用，追加物业管理员与两名维修员；它们没有房间管理或运营权限。原有学生/房管/运营身份保持原权限。

来源与清理条件见 [身份实施记录](docs/auth-integration.md)、[依赖登记](DEPENDENCIES.json)和 [M3 适配记录](../../../../../services/m3/docs/develop-integration.md)。身份服务失败不能回退开发身份。
