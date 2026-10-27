"""TEMPORARY-DEPENDENCY M3-D-DEV: synthetic D identity and resource directory.

Only explicitly activated development/test environments may use these identities.
No user-provided role or user ID is trusted; tokens select server-side records.
"""
from .ports import Actor

IDENTITIES = [
    ("demo-reporter", Actor("reporter-1", "同学一", "reporter")),
    ("demo-reporter-2", Actor("reporter-2", "同学二", "reporter")),
    ("demo-admin", Actor("admin-1", "物业管理员", "admin")),
    ("demo-technician", Actor("technician-1", "维修员一", "technician")),
    ("demo-technician-2", Actor("technician-2", "维修员二", "technician")),
    # Same stable IDs as the shared Web development session. These public
    # fixtures remain local to M3 and confer no rights in real D or M1.
    ("dev-student-cs", Actor("dev-student-cs", "计算机学院学生", "reporter",
                             frozenset({"seat:reserve"}), "cs")),
    ("dev-student-ee", Actor("dev-student-ee", "电子学院学生", "reporter",
                             frozenset({"seat:reserve"}), "ee")),
    ("dev-repair-admin", Actor("dev-repair-admin", "维修管理员", "admin",
                               frozenset({"repair:dispatch", "repair:report"}))),
    ("dev-technician-1", Actor("dev-technician-1", "维修员一", "technician",
                               frozenset({"repair:work", "repair:report"}))),
    ("dev-technician-2", Actor("dev-technician-2", "维修员二", "technician",
                               frozenset({"repair:work", "repair:report"}))),
]


class DevelopmentDirectory:
    def authenticate(self, token):
        return next((actor for key, actor in IDENTITIES if key == token), None)

    def rooms(self, actor):
        return [{"id": "room-101", "name": "第一教学楼 101 自习室"},
                {"id": "room-202", "name": "第二教学楼 202 自习室"}]

    def technicians(self, actor):
        return [a for _, a in IDENTITIES if a.role == "technician"]

    def demo_identities(self):
        return [dict(a.public(), token=token) for token, a in IDENTITIES]
