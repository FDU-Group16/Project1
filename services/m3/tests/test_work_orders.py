"""Behavior tests use the real M3 state machine, persistence, and worker."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread

from pydantic import ValidationError
from sqlalchemy import select

from services.m3.database import Database
from services.m3.dev_dependencies import DevelopmentDirectory, DevelopmentGateway
from services.m3.migrations.v0001 import outbox
from services.m3.models import CreateOrder, Problem, Rate, Command
from services.m3.ports import GatewayFailure
from services.m3.service import WorkOrders
from services.m3.worker import Worker


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


class CaptureGateway(DevelopmentGateway):
    """TEMPORARY-DEPENDENCY TEMP-M3-M1-01: inspect consumer requests only."""
    def __init__(self):
        self.calls = []
        self.failure = None

    def put(self, source_id, payload, correlation_id):
        self.calls.append((source_id, payload.copy(), correlation_id))
        if self.failure:
            raise self.failure
        return super().put(source_id, payload, correlation_id)


class WorkOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.url = 'sqlite:///' + str(Path(self.temp.name) / 'm3.db')
        self.db = Database(self.url, allow_sqlite=True)
        self.db.migrate()
        self.directory = DevelopmentDirectory()
        self.clock = Clock()
        self.service = WorkOrders(self.db, self.directory, clock=self.clock)
        self.student = self.directory.authenticate('demo-student')
        self.other = self.directory.authenticate('demo-student-2')
        self.dispatcher = self.directory.authenticate('demo-dispatcher')
        self.technician = self.directory.authenticate('demo-technician')
        self.gateway = CaptureGateway()
        self.worker = Worker(self.service, self.gateway)
        self.create_body = CreateOrder(roomId='room-101', title='灯具故障',
                                      description='靠窗照明灯持续闪烁。', category='electrical')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def create(self, key='report-1', actor=None):
        return self.service.create(actor or self.student, self.create_body, key)

    def action(self, order, action, actor=None, **values):
        return self.service.command(actor or self.student, order['id'], action,
                                    {'version': order['version'], **values})

    def assigned(self, key='report-1'):
        return self.action(self.create(key), 'assign', self.dispatcher,
                           assigneeId=self.technician.id)

    def repairing(self, key='report-1'):
        order = self.action(self.assigned(key), 'start', self.technician)
        self.assertEqual(order['status'], 'STARTING_REPAIR')
        self.assertTrue(self.worker.run_once())
        return self.service.get(self.student, order['id'])

    def assertProblem(self, code, function, *args, **kwargs):
        with self.assertRaises(Problem) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_complete_reject_accept_rate_lifecycle_preserves_block_until_accept(self):
        order = self.repairing()
        self.assertEqual(order['status'], 'IN_PROGRESS')
        self.assertEqual(self.gateway.calls[0][1]['status'], 'ACTIVE')
        order = self.action(order, 'complete', self.technician, resolution='更换灯管。')
        self.assertEqual(order['status'], 'PENDING_ACCEPTANCE')
        self.assertFalse(self.worker.run_once())
        order = self.action(order, 'reject', reason='仍然闪烁，请复查。')
        self.assertEqual(order['status'], 'IN_PROGRESS')
        self.assertFalse(self.worker.run_once())
        order = self.action(order, 'complete', self.technician, resolution='已修复线路。')
        order = self.action(order, 'accept')
        self.assertEqual(order['status'], 'ACCEPTING')
        self.worker.run_once()
        order = self.service.get(self.student, order['id'])
        self.assertEqual(order['status'], 'CLOSED')
        release = self.gateway.calls[-1]
        self.assertEqual(release[0], order['id'])
        self.assertEqual(release[1], {**self.gateway.calls[0][1], 'status': 'RELEASED', 'revision': 2})
        order = self.action(order, 'rate', rating=4, comment='已恢复正常。')
        self.assertEqual((order['rating'], order['comment']), (4, '已恢复正常。'))
        self.assertProblem('ALREADY_RATED', self.action, order, 'rate', rating=5, comment='')
        self.assertTrue(any(h['action'] == 'REJECT' for h in order['history']))

    def test_visibility_and_permissions_enforced_by_service(self):
        order = self.create()
        self.assertEqual(self.service.list(self.other), [])
        self.assertProblem('NOT_FOUND', self.service.get, self.other, order['id'])
        self.assertProblem('FORBIDDEN', self.action, order, 'assign', assigneeId=self.technician.id)
        order = self.action(order, 'assign', self.dispatcher, assigneeId=self.technician.id)
        self.assertEqual(self.service.list(self.technician)[0]['id'], order['id'])
        self.assertProblem('FORBIDDEN', self.action, order, 'start', self.dispatcher)
        order = self.action(order, 'start', self.technician)
        self.assertProblem('INVALID_STATE', self.action, order, 'cancel', reason='取消')
        self.worker.run_once()
        order = self.service.get(self.student, order['id'])
        order = self.action(order, 'complete', self.technician, resolution='修复')
        self.assertProblem('FORBIDDEN', self.action, order, 'accept', self.technician)
        self.assertProblem('FORBIDDEN', self.action, order, 'accept', self.dispatcher)

    def test_idempotency_is_actor_scoped_and_fingerprint_checked(self):
        first = self.create()
        self.assertEqual(self.create()['id'], first['id'])
        self.assertNotEqual(self.create(actor=self.other)['id'], first['id'])
        changed = self.create_body.model_copy(update={'title': '其他故障'})
        self.assertProblem('IDEMPOTENCY_CONFLICT', self.service.create,
                           self.student, changed, 'report-1')
        self.assertEqual(len(self.service.list(self.student)), 1)
        self.assertProblem('INVALID_IDEMPOTENCY_KEY', self.create, 'contains spaces')

    def test_concurrent_creation_and_old_version_produce_no_lost_updates(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            created = list(pool.map(lambda _: self.create(), range(8)))
        self.assertEqual(len({o['id'] for o in created}), 1)
        order = created[0]
        def assign(_):
            try:
                return self.action(order, 'assign', self.dispatcher, assigneeId=self.technician.id)
            except Problem as problem:
                return problem.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(assign, range(2)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertIn('VERSION_CONFLICT', results)

    def test_cancel_is_early_only_and_has_no_writeback(self):
        order = self.action(self.assigned(), 'cancel', reason='重复上报。')
        self.assertEqual(order['status'], 'CANCELLED')
        self.assertIsNone(order['dueAt'])
        self.clock.advance(days=10)
        self.assertEqual(self.service.escalate_due(), 0)
        self.assertFalse(self.worker.run_once())
        self.assertProblem('INVALID_STATE', self.action, order, 'rate', rating=5, comment='')

    def test_sla_exact_boundary_and_reassignment_cannot_postpone(self):
        order = self.create()
        self.clock.advance(hours=24, microseconds=-1)
        self.assertEqual(self.service.escalate_due(), 0)
        self.clock.advance(microseconds=1)
        self.assertEqual(self.service.escalate_due(), 1)
        self.assertEqual(self.service.escalate_due(), 0)
        order = self.service.get(self.student, order['id'])
        self.assertTrue(order['escalated'])
        self.assertEqual(order['status'], 'REPORTED')
        order = self.action(order, 'assign', self.dispatcher, assigneeId=self.technician.id)
        self.assertFalse(order['escalated'])
        deadline = order['dueAt']
        self.clock.advance(hours=47)
        order = self.action(order, 'assign', self.dispatcher, assigneeId='technician-2')
        self.assertEqual(order['dueAt'], deadline)
        self.clock.advance(hours=1)
        self.assertEqual(self.service.escalate_due(), 1)
        latest = self.service.get(self.student, order['id'])
        self.assertEqual(len([h for h in latest['history'] if h['action'] == 'ESCALATED']), 2)

    def test_pending_writeback_and_idempotency_survive_restart(self):
        order = self.action(self.assigned(), 'start', self.technician)
        self.db.close()
        self.db = Database(self.url, allow_sqlite=True)
        self.db.migrate()
        self.db.check_schema()
        self.service = WorkOrders(self.db, self.directory, clock=self.clock)
        worker = Worker(self.service, self.gateway)
        self.assertEqual(self.create()['id'], order['id'])
        self.assertTrue(worker.run_once())
        self.assertEqual(self.service.get(self.student, order['id'])['status'], 'IN_PROGRESS')
        self.assertFalse(worker.run_once())

    def test_transient_failures_retry_same_payload_then_require_manual_retry(self):
        order = self.action(self.assigned(), 'start', self.technician)
        self.gateway.failure = GatewayFailure('M1_HTTP_503', True)
        for _ in range(5):
            self.assertTrue(self.worker.run_once())
            self.clock.advance(minutes=2)
        failed = self.service.get(self.student, order['id'])
        self.assertEqual(failed['status'], 'STARTING_REPAIR')
        self.assertEqual(failed['syncStatus'], 'FAILED')
        self.assertFalse(self.worker.run_once())
        self.assertTrue(all(call == self.gateway.calls[0] for call in self.gateway.calls))
        self.assertProblem('FORBIDDEN', self.action, failed, 'retry-sync', reason='重试')
        failed = self.action(failed, 'retry-sync', self.dispatcher, reason='已确认 M1 恢复。')
        self.gateway.failure = None
        self.worker.run_once()
        self.assertEqual(self.gateway.calls[-1], self.gateway.calls[0])
        self.assertEqual(self.service.get(self.student, order['id'])['status'], 'IN_PROGRESS')

    def test_permanent_failure_never_retries_or_advances_business_state(self):
        order = self.action(self.assigned(), 'start', self.technician)
        self.gateway.failure = GatewayFailure('M1_HTTP_409', False)
        self.worker.run_once()
        self.clock.advance(days=1)
        self.assertFalse(self.worker.run_once())
        failed = self.service.get(self.student, order['id'])
        self.assertEqual((failed['status'], failed['syncStatus']), ('STARTING_REPAIR', 'FAILED'))
        self.assertProblem('RECONCILIATION_REQUIRED', self.action, failed, 'retry-sync',
                           self.dispatcher, reason='重试')

    def test_worker_ack_preserves_concurrent_escalation_and_no_duplicate_history(self):
        order = self.action(self.assigned(), 'start', self.technician)
        entered, release = Event(), Event()
        gateway = self.gateway
        class SlowGateway:
            def put(self, *args):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test deadline')
                return gateway.put(*args)
        worker = Worker(self.service, SlowGateway())
        thread = Thread(target=worker.run_once)
        thread.start()
        self.assertTrue(entered.wait(3))
        self.clock.advance(hours=49)
        self.assertEqual(self.service.escalate_due(), 1)
        release.set()
        thread.join(5)
        latest = self.service.get(self.student, order['id'])
        self.assertTrue(latest['escalated'])
        self.assertEqual(latest['status'], 'IN_PROGRESS')
        self.assertEqual(len([h for h in latest['history'] if h['action'] == 'M1_ACTIVE_CONFIRMED']), 1)
        self.assertFalse(self.worker.run_once())

    def test_multiple_orders_have_independent_sources(self):
        first, second = self.repairing('first'), self.repairing('second')
        first = self.action(first, 'complete', self.technician, resolution='修好')
        first = self.action(first, 'accept')
        self.worker.run_once()
        self.assertEqual(self.gateway.calls[-1][0], first['id'])
        self.assertEqual(self.service.get(self.student, second['id'])['status'], 'IN_PROGRESS')
        self.assertFalse(any(call[0] == second['id'] and call[1]['status'] == 'RELEASED'
                             for call in self.gateway.calls))

    def test_request_validation_rejects_extra_identity_blank_and_boolean_integers(self):
        data = self.create_body.model_dump()
        for update in ({'title': '  '}, {'reporterId': 'spoof'}, {'roles': ['dispatcher']},
                       {'description': 'x' * 2001}, {'category': 'bad'}):
            with self.assertRaises(ValidationError):
                CreateOrder(**{**data, **update})
        for body in ({'version': True}, {'version': 1.0}, {'version': '1'}):
            with self.assertRaises(ValidationError):
                Command(**body)
        for rating in (0, 6, True, '5', 2.5):
            with self.assertRaises(ValidationError):
                Rate(version=1, rating=rating)
        invalid = self.create_body.model_copy(update={'roomId': 'nonexistent'})
        self.assertProblem('INVALID_ROOM', self.service.create, self.student, invalid, 'new')


if __name__ == '__main__':
    unittest.main()
