"""Real M3 behavior. Provider stand-ins may be injected, never domain stand-ins."""

import hashlib
import json
import re
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import insert, or_, select, update

from .database import Database
from .migrations.v0001 import keys, orders, outbox
from .models import Actor, CreateOrder, Problem, timestamp, utc_now
from .ports import Directory


class WorkOrders:
    def __init__(self, database: Database, directory: Directory, *, clock=utc_now,
                 assignment_hours=24.0, repair_hours=48.0):
        self.database, self.directory, self.clock = database, directory, clock
        self.assignment_hours, self.repair_hours = assignment_hours, repair_hours

    @staticmethod
    def visible(actor: Actor, order: dict) -> bool:
        return ('dispatcher' in actor.roles or order['reporterId'] == actor.id
                or ('technician' in actor.roles and order['assigneeId'] == actor.id))

    def require_dispatcher(self, actor: Actor):
        if 'dispatcher' not in actor.roles:
            raise Problem(403, 'FORBIDDEN', '此操作需要工单调度权限。')

    def _get(self, connection, order_id: str) -> dict:
        row = connection.execute(select(orders.c.body).where(orders.c.id == order_id)).first()
        if row is None:
            raise Problem(404, 'NOT_FOUND', '工单不存在或不可访问。')
        return json.loads(row.body)

    def _visible_order(self, connection, actor: Actor, order_id: str) -> dict:
        order = self._get(connection, order_id)
        if not self.visible(actor, order):
            raise Problem(404, 'NOT_FOUND', '工单不存在或不可访问。')
        return order

    @staticmethod
    def _public(order: dict) -> dict:
        return {k: v for k, v in order.items() if not k.startswith('_')}

    def get(self, actor: Actor, order_id: str) -> dict:
        with self.database.read() as connection:
            return self._public(self._visible_order(connection, actor, order_id))

    def list(self, actor: Actor) -> list[dict]:
        query = select(orders.c.body).order_by(orders.c.created_at.desc(), orders.c.id.desc())
        if 'dispatcher' not in actor.roles:
            criteria = orders.c.reporter_id == actor.id
            if 'technician' in actor.roles:
                criteria = or_(criteria, orders.c.assignee_id == actor.id)
            query = query.where(criteria)
        with self.database.read() as connection:
            return [self._public(json.loads(row.body)) for row in connection.execute(query)]

    def save(self, connection, order: dict):
        connection.execute(update(orders).where(orders.c.id == order['id']).values(
            assignee_id=order['assigneeId'], body=json.dumps(order, ensure_ascii=False)))

    @staticmethod
    def event(order: dict, action: str, actor_id: str, now: str, detail: str):
        order['history'].append({'action': action, 'actorId': actor_id, 'at': now, 'detail': detail})
        order['updatedAt'] = now
        order['version'] += 1

    def create(self, actor: Actor, body: CreateOrder, key: str) -> dict:
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', key):
            raise Problem(422, 'INVALID_IDEMPOTENCY_KEY', '幂等键须为 1～128 位字母、数字或 ._:-。')
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
        # A previously accepted request remains replayable even if the room
        # directory changes later. Recheck under the write lock below for races.
        with self.database.read() as connection:
            existing = connection.execute(select(keys).where(
                keys.c.actor_id == actor.id, keys.c.key == key)).mappings().first()
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise Problem(409, 'IDEMPOTENCY_CONFLICT', '该幂等键已用于不同的报修内容。')
                return self._public(self._get(connection, existing['order_id']))
        # Directory lookup is outside the write transaction. No provider I/O under lock.
        room = next((r for r in self.directory.rooms(actor) if r.id == body.roomId), None)
        if room is None:
            raise Problem(422, 'INVALID_ROOM', '请选择当前身份可报修的有效房间。')
        with self.database.transaction() as connection:
            existing = connection.execute(select(keys).where(
                keys.c.actor_id == actor.id, keys.c.key == key)).mappings().first()
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise Problem(409, 'IDEMPOTENCY_CONFLICT', '该幂等键已用于不同的报修内容。')
                return self._public(self._get(connection, existing['order_id']))
            now = self.clock()
            at = timestamp(now)
            order = {'id': str(uuid4()), 'roomId': room.id, 'roomName': room.name,
                **body.model_dump(exclude={'roomId'}), 'reporterId': actor.id, 'assigneeId': None,
                'status': 'REPORTED', 'version': 1, 'createdAt': at, 'updatedAt': at,
                'dueAt': timestamp(now + timedelta(hours=self.assignment_hours)),
                'escalated': False, 'rating': None, 'comment': None, 'resolution': None,
                'syncStatus': 'NONE', 'syncError': None,
                'history': [{'action': 'REPORTED', 'actorId': actor.id, 'at': at, 'detail': '已提交故障上报。'}],
                '_blockRevision': 0, '_blockStartsAt': None}
            connection.execute(insert(orders).values(id=order['id'], reporter_id=actor.id,
                assignee_id=None, created_at=at, body=json.dumps(order, ensure_ascii=False)))
            connection.execute(insert(keys).values(actor_id=actor.id, key=key,
                fingerprint=fingerprint, order_id=order['id']))
            return self._public(order)

    def _enqueue(self, connection, order: dict, status: str, now: str):
        order['_blockRevision'] += 1
        if order['_blockStartsAt'] is None:
            order['_blockStartsAt'] = now
        payload = {'roomId': order['roomId'], 'revision': order['_blockRevision'],
                   'status': status, 'startsAt': order['_blockStartsAt']}
        connection.execute(insert(outbox).values(id=str(uuid4()), order_id=order['id'],
            revision=payload['revision'], payload=json.dumps(payload), correlation_id=str(uuid4()),
            status='PENDING', attempts=0, next_attempt_at=now, lease_id=None,
            last_error=None, retryable=0, receipt=None))
        order['syncStatus'], order['syncError'] = 'PENDING', None

    def command(self, actor: Actor, order_id: str, action: str, body: dict) -> dict:
        # Validate assignee against provider before taking a DB lock.
        if action == 'assign':
            self.require_dispatcher(actor)
            if body['assigneeId'] not in {a.id for a in self.directory.technicians()}:
                raise Problem(422, 'INVALID_ASSIGNEE', '请选择有效的维修人员。')
        with self.database.transaction() as connection:
            order = self._visible_order(connection, actor, order_id)
            if action in ('assign', 'retry-sync'):
                self.require_dispatcher(actor)
            elif action in ('start', 'complete'):
                if 'technician' not in actor.roles or order['assigneeId'] != actor.id:
                    raise Problem(403, 'FORBIDDEN', '仅当前受派维修人员可执行此操作。')
            elif action in ('accept', 'reject', 'cancel', 'rate'):
                if order['reporterId'] != actor.id:
                    raise Problem(403, 'FORBIDDEN', '仅工单上报者可执行此操作。')
            else:
                raise Problem(422, 'UNKNOWN_ACTION', '未知工单操作。')
            if order['version'] != body['version']:
                raise Problem(409, 'VERSION_CONFLICT', '工单已更新，请刷新后重试。')
            allowed = {'assign': {'REPORTED', 'ASSIGNED'}, 'start': {'ASSIGNED'},
                'complete': {'IN_PROGRESS'}, 'accept': {'PENDING_ACCEPTANCE'},
                'reject': {'PENDING_ACCEPTANCE'}, 'cancel': {'REPORTED', 'ASSIGNED'},
                'rate': {'CLOSED'}, 'retry-sync': {'STARTING_REPAIR', 'ACCEPTING'}}
            if order['status'] not in allowed[action]:
                raise Problem(409, 'INVALID_STATE', '当前工单状态不允许此操作。')
            now_dt = self.clock()
            now = timestamp(now_dt)
            detail = ''
            if action == 'assign':
                if body['assigneeId'] == order['reporterId']:
                    raise Problem(422, 'SELF_REPAIR_FORBIDDEN', '维修人员不能兼任本工单的上报验收者。')
                reassignment = order['status'] == 'ASSIGNED'
                order['assigneeId'], order['status'] = body['assigneeId'], 'ASSIGNED'
                # Reassignment must not indefinitely postpone the repair SLA.
                if not reassignment:
                    order['dueAt'] = timestamp(now_dt + timedelta(hours=self.repair_hours))
                    order['escalated'] = False
                detail = f'已派给 {body["assigneeId"]}。'
            elif action == 'start':
                order['status'] = 'STARTING_REPAIR'
                self._enqueue(connection, order, 'ACTIVE', now)
                detail = '等待 M1 确认维修下架；确认前尚未进入维修中。'
            elif action == 'complete':
                order['status'], order['resolution'] = 'PENDING_ACCEPTANCE', body['resolution']
                order['dueAt'] = None
                detail = body['resolution']
            elif action == 'accept':
                order['status'] = 'ACCEPTING'
                self._enqueue(connection, order, 'RELEASED', now)
                detail = '验收通过，等待 M1 确认撤销本工单阻断。'
            elif action == 'reject':
                order['status'] = 'IN_PROGRESS'
                order['dueAt'] = timestamp(now_dt + timedelta(hours=self.repair_hours))
                order['escalated'] = False
                detail = body['reason']
            elif action == 'cancel':
                order['status'], order['dueAt'] = 'CANCELLED', None
                detail = body['reason']
            elif action == 'rate':
                if order['rating'] is not None:
                    raise Problem(409, 'ALREADY_RATED', '该工单已评价。')
                order['rating'], order['comment'] = body['rating'], body['comment']
                detail = f'{body["rating"]} 星；{body["comment"]}'
            elif action == 'retry-sync':
                job = connection.execute(select(outbox).where(outbox.c.order_id == order_id,
                    outbox.c.revision == order['_blockRevision'])).mappings().first()
                if not job or job['status'] != 'FAILED' or not job['retryable']:
                    raise Problem(409, 'RECONCILIATION_REQUIRED', '此错误须先与 M1 核对处理，不能盲目重试。')
                connection.execute(update(outbox).where(outbox.c.id == job['id']).values(
                    status='PENDING', attempts=0, next_attempt_at=now, lease_id=None))
                order['syncStatus'], order['syncError'] = 'PENDING', None
                detail = body['reason']
            self.event(order, action.upper().replace('-', '_'), actor.id, now, detail)
            self.save(connection, order)
            return self._public(order)

    def escalate_due(self) -> int:
        changed = 0
        with self.database.transaction() as connection:
            now = timestamp(self.clock())
            for row in connection.execute(select(orders.c.body)).all():
                order = json.loads(row.body)
                if (order['status'] in {'REPORTED', 'ASSIGNED', 'STARTING_REPAIR', 'IN_PROGRESS'}
                    and order['dueAt'] is not None and order['dueAt'] <= now and not order['escalated']):
                    order['escalated'] = True
                    self.event(order, 'ESCALATED', 'system', now,
                        '已超过当前阶段 SLA，升级至物业调度；公共通知尚未接入，未声明送达。')
                    self.save(connection, order)
                    changed += 1
        return changed
