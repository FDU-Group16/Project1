"""TEMPORARY-DEPENDENCY: TEMP-M3-D-01 / TEMP-M3-M1-01.

Synthetic identities/rooms and minimal M1 receipts, only explicit development.
This is NOT D authentication, notification delivery, or real seat writeback.
Cleanup ownership and trigger: docs/2026-10-26-implementation.md.
"""

from .models import Actor, DirectoryItem, Problem, timestamp, utc_now


class DevelopmentDirectory:
    def __init__(self):
        self.actors = {
            'demo-student': Actor(id='student-1', name='演示同学一', roles=['student']),
            'demo-student-2': Actor(id='student-2', name='演示同学二', roles=['student']),
            'demo-dispatcher': Actor(id='dispatcher-1', name='演示调度员', roles=['dispatcher']),
            'demo-technician': Actor(id='technician-1', name='演示维修员一', roles=['technician']),
            'demo-technician-2': Actor(id='technician-2', name='演示维修员二', roles=['technician']),
        }

    def authenticate(self, token: str) -> Actor:
        actor = self.actors.get(token)
        if actor is None:
            raise Problem(401, 'INVALID_IDENTITY', '登录凭据无效。')
        return actor.model_copy(deep=True)

    def rooms(self, actor: Actor) -> list[DirectoryItem]:
        return [DirectoryItem(id='room-101', name='演示自习室 101'),
                DirectoryItem(id='room-102', name='演示自习室 102')]

    def technicians(self) -> list[DirectoryItem]:
        return [DirectoryItem(id=a.id, name=a.name) for a in self.actors.values()
                if 'technician' in a.roles]


class DevelopmentGateway:
    """Only echoes a receipt. Does not model seats or claim M1 integration."""
    def put(self, source_id: str, payload: dict, correlation_id: str) -> dict:
        return {**payload, 'sourceSystem': 'M3', 'sourceId': source_id,
                'appliedAt': timestamp(utc_now())}
