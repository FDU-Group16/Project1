"""TEMPORARY-DEPENDENCY D02-IDENTITY. Synthetic consumer test identities."""

IDENTITIES = {
    "dev-student-cs": {"id": "dev-student-cs", "departmentId": "cs", "permissions": ["seat:reserve"]},
    "dev-student-ee": {"id": "dev-student-ee", "departmentId": "ee", "permissions": ["seat:reserve"]},
    "dev-room-admin": {"id": "dev-room-admin", "departmentId": None, "permissions": ["room:manage"]},
    "dev-operator": {"id": "dev-operator", "departmentId": None, "permissions": ["operations:read"]},
}


def identify(token: str) -> dict | None:
    value = IDENTITIES.get(token)
    return {**value, "permissions": list(value["permissions"])} if value else None
