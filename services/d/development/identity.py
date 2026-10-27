"""TEMPORARY-DEPENDENCY D02-IDENTITY：D-02 消费 D-01 的合成身份替身。

由 M1 为 D-02 并行开发维护；D-01 由 M2 负责，M1/M2 可协调修改或替换。
真实身份联调通过后按 ../tasks/2026-10-22-d02.md 清理本文件和开发接入分支；
保留 D-02 主数据业务、真实身份客户端及权限/错误处理。
"""

IDENTITIES = {
    "dev-student-cs": {"id": "dev-student-cs", "departmentId": "cs", "permissions": ["seat:reserve"]},
    "dev-student-ee": {"id": "dev-student-ee", "departmentId": "ee", "permissions": ["seat:reserve"]},
    "dev-room-admin": {"id": "dev-room-admin", "departmentId": None, "permissions": ["room:manage"]},
    "dev-operator": {"id": "dev-operator", "departmentId": None, "permissions": ["operations:read"]},
}


def identify(token: str) -> dict | None:
    value = IDENTITIES.get(token)
    return {**value, "permissions": list(value["permissions"])} if value else None
