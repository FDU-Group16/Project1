# D-02 房间与座位主数据 HTTP 契约

版本：`0.1.0`；状态：**proposed，已按当前任务实现，仍待受影响组评审**。机器可读定义见 [OpenAPI](d-master-data.openapi.json)。实现不表示 D 的职责提案或身份契约已获团队批准。

## 边界与身份

D 只保存基础事实；预约、整室审批占用和维修来源由 M1 管理。稳定 `id` 是不复用的字符串，正常创建由服务器生成 UUID。座位 `number` 在同一房间中唯一，注销也不释放编号。所有修改要求经 D-01 验证的 `room:manage` 权限；查询要求登录。学生只能读取公共房间（`departmentId=null`）或同院系的有效房间及有效座位，直接访问其他房间返回 403。停用或注销的房间对学生返回 404。`room:manage` 和 `operations:read` 可读取全部基础数据，后者不能修改。

D-01 尚无已批准的当前身份接口；消费方暂定 `GET ${D_IDENTITY_URL}/api/v1/auth/me`，转发 `Authorization: Bearer …`，返回 `{id, departmentId, permissions}`；`departmentId` 为字符串或 null，`permissions` 为字符串数组。认证失败返回 401，依赖不可用或非法响应返回 503，绝不回退为演示身份。该假设待 M2 组协调。D-02 的替身仅在 `APP_ENV=development|test` 且 `D_USE_DEV_IDENTITY=1` 时启用，详见 D 任务记录。

M1 内部查询使用独立服务凭据：`Authorization: Bearer ${D_M1_TOKEN}`。未配置令牌返回 503，错误令牌返回 401。内部列表和详情包含所有停用、注销房间和座位，使 M1 能在预约时重新校验。它不授予修改能力。

## 数据和开放时间

房间字段为 `id,name,departmentId,openHour,closeHour,weekdays,active,retired`；座位字段为 `id,roomId,number,hasSocket,active,retired`。`name` 长度 1–120，`number` 长度 1–40；去除首尾空白后不能为空。`departmentId` 为 null 或非空字符串，最长 80。

开放时间按 **Asia/Shanghai** 每日解释：整数 `0 <= openHour < closeHour <= 24`，区间为 `[openHour,closeHour)`，不跨午夜；`weekdays` 是 0（周一）到 6（周日）的非空、无重复数组。`closeHour=24` 是次日零点。M1 将 UTC 预约时间转换至此时区校验完整预约区间，必须落在同一开放日。未声明跨日或节假日例外。

`active=false` 是可逆停用；`DELETE` 为不可逆注销（`retired=true,active=false`），保留记录和稳定引用。注销房间同时注销全部座位；重复 DELETE 返回同一注销状态。已注销实体的 PATCH 或在注销房间新增座位返回 409；不能通过 PATCH 恢复。停用房间不会修改座位自身标记。修改房间不会自动取消现有 M1 预约；M1 负责后续查询和新预约校验，存量预约治理需另行任务。

## 接口

| 方法和路径 | 行为 |
| --- | --- |
| `GET /api/v1/rooms` | 可见房间 `{items:[Room]}`；管理员和运营读取全部 |
| `POST /api/v1/rooms` | 管理员创建房间；201 Room |
| `GET /api/v1/rooms/{roomId}` | 按身份范围读取 Room |
| `PATCH /api/v1/rooms/{roomId}` | 管理员部分修改；200 Room |
| `DELETE /api/v1/rooms/{roomId}` | 管理员注销房间及其座位；200 Room |
| `GET /api/v1/rooms/{roomId}/seats` | 按房间范围查询座位 `{items:[Seat]}` |
| `POST /api/v1/rooms/{roomId}/seats` | 管理员创建座位；201 Seat |
| `PATCH /api/v1/seats/{seatId}` | 管理员修改编号、插座、可用性；200 Seat |
| `DELETE /api/v1/seats/{seatId}` | 管理员注销座位；200 Seat |
| `GET /internal/v1/rooms` | M1 查询 `{items:[RoomWithSeats]}`，包含全部状态 |
| `GET /internal/v1/rooms/{roomId}` | M1 查询 RoomWithSeats，包含全部状态 |

创建时 `active` 默认 true，座位 `hasSocket` 默认 false；房间开放小时、weekdays、name 必填，`departmentId` 默认 null。PATCH 至少提供一个允许字段；不接受未知字段、id、roomId 或 retired。响应排序按房间 name/id、座位 number/id 稳定排序。当前首版列表不分页；数量增大后新增向后兼容分页参数。

## 错误、兼容性与验证

错误响应包含 `code` 和 `detail`；验证失败为 422。401 认证失败；403 无权限/院系越权；404 不存在或学生不可见的停用实体；409 编号冲突/已注销；503 数据库或身份依赖不可用。修改不接受重试幂等键；客户端对未知 POST 结果应先查询再由人工确认重试，避免重复建立实体。DELETE 幂等。

这是新增 v1 接口，无旧业务客户端需要迁移。DDL 位于 D 自有 schema，版本化迁移与合成演示种子分离。主数据真实 PostgreSQL 行为、权限边界、注销不可恢复和网络 M1 读取的证据由 [D 状态](../services/d/STATUS.md) 单独记录。身份替身测试不能证明真实 D-01 已可用。
