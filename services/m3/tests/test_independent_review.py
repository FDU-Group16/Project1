"""Independent M3 behavioral review.

The local HTTP server and DevelopmentDirectory are explicit provider test doubles.
M3's HTTP adapter, validation, authorization and persisted domain behavior are real.
These tests do not establish that the actual M1 or D service is available.
"""

import asyncio
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import event, select

from services.m3.database import Database
from services.m3.dev_dependencies import DevelopmentDirectory
from services.m3.m1_client import HttpBlockGateway, validate_receipt
from services.m3.migrations.v0001 import outbox
from services.m3.models import Command, Complete, CreateOrder, Problem, Rate, Reason
from services.m3.ports import GatewayFailure, UnavailableDirectory
from services.m3.service import WorkOrders
from services.m3.settings import Settings
from services.m3.worker import Worker


SOURCE = 'work-order-independent-review'
PAYLOAD = {
    'roomId': 'room-101', 'revision': 1, 'status': 'ACTIVE',
    'startsAt': '2026-10-26T08:00:00.000000Z',
}


def valid_receipt():
    return {
        **PAYLOAD, 'sourceSystem': 'M3', 'sourceId': SOURCE,
        'appliedAt': '2026-10-26T08:00:01.000000Z',
    }


class ReceiptReviewTests(unittest.TestCase):
    def test_accepts_exact_active_and_released_receipts(self):
        validate_receipt(SOURCE, PAYLOAD, valid_receipt())
        released = {**PAYLOAD, 'revision': 2, 'status': 'RELEASED'}
        receipt = {**valid_receipt(), **released}
        validate_receipt(SOURCE, released, receipt)

    def test_rejects_wrong_source_room_state_revision_or_interval(self):
        invalid_values = {
            'sourceSystem': ['M2', None], 'sourceId': ['another-order', None],
            'roomId': ['room-102', None], 'revision': [2, True, '1', 1.0, None],
            'status': ['RELEASED', None],
            'startsAt': ['2026-10-26T09:00:00.000000Z', None],
        }
        for key, values in invalid_values.items():
            for value in values:
                with self.subTest(field=key, value=value):
                    receipt = {**valid_receipt(), key: value}
                    with self.assertRaises(GatewayFailure) as raised:
                        validate_receipt(SOURCE, PAYLOAD, receipt)
                    self.assertFalse(raised.exception.retryable)

    def test_rejects_missing_fields_nonobjects_and_invented_interval_end(self):
        invalid = [None, [], 'success', 1, True]
        for key in valid_receipt():
            receipt = valid_receipt()
            del receipt[key]
            invalid.append(receipt)
        invalid.extend([
            {**valid_receipt(), 'endsAt': None},
            {**valid_receipt(), 'endsAt': '2026-10-27T08:00:00Z'},
        ])
        for receipt in invalid:
            with self.subTest(receipt=receipt):
                with self.assertRaises(GatewayFailure):
                    validate_receipt(SOURCE, PAYLOAD, receipt)

    def test_rejects_invalid_or_non_rfc3339_applied_time(self):
        for applied in [None, '', 'yesterday', '2026-02-30T08:00:00Z',
                        '2026-10-26T08:00:00+08:00', '2026-10-26T08:00:00',
                        '20261026T080000Z', '2026-W44-1T08:00:00Z']:
            with self.subTest(appliedAt=applied):
                with self.assertRaises(GatewayFailure):
                    validate_receipt(SOURCE, PAYLOAD, {
                        **valid_receipt(), 'appliedAt': applied})

    def test_rejects_unknown_fields_as_required_by_m1_contract(self):
        # AppliedBlockState explicitly has additionalProperties: false.
        with self.assertRaises(GatewayFailure):
            validate_receipt(SOURCE, PAYLOAD, {**valid_receipt(), 'unknown': True})


class NetworkReviewTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.reply_status = 200
        self.reply_body = json.dumps(valid_receipt()).encode()
        self.reply_headers = {}
        self.reply_delay = 0
        self.invalid_chunked = False
        owner = self

        class ProviderDouble(BaseHTTPRequestHandler):
            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                owner.requests.append((self.path, dict(self.headers.items()), body))
                if owner.reply_delay:
                    time.sleep(owner.reply_delay)
                self.send_response(owner.reply_status)
                if owner.invalid_chunked:
                    self.send_header('Transfer-Encoding', 'chunked')
                else:
                    self.send_header('Content-Length', str(len(owner.reply_body)))
                for key, value in owner.reply_headers.items():
                    self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(b'not-hex\r\n' if owner.invalid_chunked
                                     else owner.reply_body)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                self.close_connection = True

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), ProviderDouble)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.client = HttpBlockGateway(self.url, 'synthetic-test-service-token', timeout=0.3)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_real_put_uses_stable_path_authorization_payload_and_correlation(self):
        receipt = self.client.put(SOURCE, PAYLOAD, 'correlation-independent-review')
        self.assertEqual(receipt, valid_receipt())
        self.assertEqual(len(self.requests), 1)
        path, headers, raw = self.requests[0]
        self.assertEqual(path, f'/internal/v1/room-blocks/m3/{SOURCE}')
        self.assertEqual(headers['Authorization'], 'Bearer synthetic-test-service-token')
        self.assertEqual(headers['X-Correlation-Id'], 'correlation-independent-review')
        self.assertEqual(json.loads(raw), PAYLOAD)

    def test_status_classification_without_leaking_provider_response(self):
        for status, retryable in [(401, False), (403, False), (404, False),
                                  (409, False), (422, False), (502, True),
                                  (503, True), (504, True)]:
            with self.subTest(status=status):
                self.reply_status = status
                self.reply_body = b'private upstream body and synthetic-test-service-token'
                with self.assertRaises(GatewayFailure) as raised:
                    self.client.put(SOURCE, PAYLOAD, 'request-errors')
                self.assertEqual(raised.exception.code, f'M1_HTTP_{status}')
                self.assertEqual(raised.exception.retryable, retryable)
                self.assertNotIn('private', str(raised.exception))
                self.assertNotIn('synthetic-test-service-token', str(raised.exception))

    def test_redirect_is_rejected_without_forwarding_credentials(self):
        self.reply_status = 307
        self.reply_headers = {'Location': f'{self.url}/redirect-target'}
        with self.assertRaises(GatewayFailure) as raised:
            self.client.put(SOURCE, PAYLOAD, 'request-redirect')
        self.assertEqual(raised.exception.code, 'M1_HTTP_307')
        self.assertEqual(len(self.requests), 1)

    def test_malformed_and_oversized_success_responses_are_not_success(self):
        for raw in [b'not json', b'\xff', b'[]', b'null', b' ' * 65537]:
            with self.subTest(response_prefix=repr(raw[:20])):
                self.reply_body = raw
                with self.assertRaises(GatewayFailure) as raised:
                    self.client.put(SOURCE, PAYLOAD, 'request-malformed')
                self.assertFalse(raised.exception.retryable)

    def test_timeout_is_retryable(self):
        self.reply_delay = 0.1
        self.client.timeout = 0.02
        with self.assertRaises(GatewayFailure) as raised:
            self.client.put(SOURCE, PAYLOAD, 'request-timeout')
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(raised.exception.code, 'M1_NETWORK_UNAVAILABLE')

    def test_malformed_chunked_transport_is_normalized_to_gateway_failure(self):
        self.invalid_chunked = True
        with self.assertRaises(GatewayFailure):
            self.client.put(SOURCE, PAYLOAD, 'request-broken-transport')

    def test_configuration_rejects_credentials_and_invalid_tokens(self):
        for url, token in [('file:///tmp/m1', 'token'),
                           ('https://user:password@example.invalid', 'token'),
                           ('https://example.invalid?token=secret', 'token'),
                           ('https://example.invalid#fragment', 'token'),
                           (self.url, ''), (self.url, 'first\nsecond')]:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    HttpBlockGateway(url, token)


class AuthorizationAndInputReviewTests(unittest.TestCase):
    def setUp(self):
        self.database = Database('sqlite:///:memory:', allow_sqlite=True)
        self.database.migrate()
        self.directory = DevelopmentDirectory()
        self.service = WorkOrders(self.database, self.directory,
            clock=lambda: datetime(2026, 10, 26, 8, tzinfo=timezone.utc))
        self.student = self.directory.authenticate('demo-student')
        self.other_student = self.directory.authenticate('demo-student-2')
        self.dispatcher = self.directory.authenticate('demo-dispatcher')
        self.technician = self.directory.authenticate('demo-technician')
        self.other_technician = self.directory.authenticate('demo-technician-2')
        self.body = CreateOrder(roomId='room-101', title='Broken desk',
                                description='A desk leg is loose.', category='furniture')
        self.order = self.service.create(self.student, self.body, 'review-create-1')

    def tearDown(self):
        self.database.close()

    def test_unrelated_users_cannot_enumerate_work_orders(self):
        for actor in [self.other_student, self.technician, self.other_technician]:
            with self.subTest(actor=actor.id):
                self.assertEqual(self.service.list(actor), [])
                with self.assertRaises(Problem) as raised:
                    self.service.get(actor, self.order['id'])
                self.assertEqual(raised.exception.status, 404)
        self.assertEqual(self.service.list(self.student)[0]['id'], self.order['id'])
        self.assertEqual(self.service.list(self.dispatcher)[0]['id'], self.order['id'])

    def test_assignment_requires_dispatcher_and_valid_assignee(self):
        with self.assertRaises(Problem) as raised:
            self.service.command(self.student, self.order['id'], 'assign',
                {'version': 1, 'assigneeId': self.technician.id})
        self.assertEqual(raised.exception.status, 403)
        with self.assertRaises(Problem) as raised:
            self.service.command(self.dispatcher, self.order['id'], 'assign',
                {'version': 1, 'assigneeId': 'missing-technician'})
        self.assertEqual(raised.exception.code, 'INVALID_ASSIGNEE')
        self.assertEqual(self.service.get(self.student, self.order['id'])['status'], 'REPORTED')

    def test_only_assignee_can_start_and_pending_start_cannot_be_completed_or_cancelled(self):
        assigned = self.service.command(self.dispatcher, self.order['id'], 'assign',
            {'version': 1, 'assigneeId': self.technician.id})
        self.assertEqual(self.service.list(self.technician)[0]['id'], self.order['id'])
        for actor in [self.student, self.dispatcher, self.other_technician]:
            with self.subTest(actor=actor.id):
                with self.assertRaises(Problem) as raised:
                    self.service.command(actor, self.order['id'], 'start',
                                         {'version': assigned['version']})
                self.assertIn(raised.exception.status, (403, 404))
        pending = self.service.command(self.technician, self.order['id'], 'start',
                                       {'version': assigned['version']})
        self.assertEqual(pending['status'], 'STARTING_REPAIR')
        self.assertEqual(pending['syncStatus'], 'PENDING')
        for actor, action, fields in [
            (self.student, 'cancel', {'reason': 'No longer needed'}),
            (self.technician, 'complete', {'resolution': 'Fixed'}),
        ]:
            with self.subTest(action=action):
                with self.assertRaises(Problem) as raised:
                    self.service.command(actor, self.order['id'], action,
                        {'version': pending['version'], **fields})
                self.assertEqual(raised.exception.code, 'INVALID_STATE')

    def test_reporter_cannot_be_their_own_assigned_technician(self):
        own = self.service.create(self.technician, self.body, 'technician-own-report')
        with self.assertRaises(Problem) as raised:
            self.service.command(self.dispatcher, own['id'], 'assign',
                {'version': own['version'], 'assigneeId': self.technician.id})
        self.assertEqual(raised.exception.code, 'SELF_REPAIR_FORBIDDEN')

    def test_create_idempotency_is_actor_scoped_and_detects_changed_content(self):
        same = self.service.create(self.student, self.body, 'review-create-1')
        self.assertEqual(same['id'], self.order['id'])
        other = self.service.create(self.other_student, self.body, 'review-create-1')
        self.assertNotEqual(other['id'], self.order['id'])
        changed = self.body.model_copy(update={'title': 'Different failure'})
        with self.assertRaises(Problem) as raised:
            self.service.create(self.student, changed, 'review-create-1')
        self.assertEqual(raised.exception.code, 'IDEMPOTENCY_CONFLICT')
        self.assertEqual(len(self.service.list(self.student)), 1)

    def test_stale_version_cannot_override_assignment(self):
        assigned = self.service.command(self.dispatcher, self.order['id'], 'assign',
            {'version': 1, 'assigneeId': self.technician.id})
        with self.assertRaises(Problem) as raised:
            self.service.command(self.student, self.order['id'], 'cancel',
                                  {'version': 1, 'reason': 'stale request'})
        self.assertEqual(raised.exception.code, 'VERSION_CONFLICT')
        self.assertEqual(self.service.get(self.student, self.order['id']), assigned)

    def test_public_models_reject_identity_injection_and_invalid_values(self):
        for extra in [{'reporterId': 'someone-else'}, {'roles': ['dispatcher']},
                      {'createdAt': '2000-01-01T00:00:00Z'}]:
            with self.subTest(extra=extra):
                with self.assertRaises(ValidationError):
                    CreateOrder(**self.body.model_dump(), **extra)
        for title in ['', ' \t\n ', 'x' * 121]:
            with self.subTest(title_length=len(title)):
                with self.assertRaises(ValidationError):
                    CreateOrder(**{**self.body.model_dump(), 'title': title})
        for version in [True, '1', 1.0, 0, -1]:
            with self.subTest(version=version):
                with self.assertRaises(ValidationError):
                    Command(version=version)
        for rating in [True, '5', 4.5, 0, 6]:
            with self.subTest(rating=rating):
                with self.assertRaises(ValidationError):
                    Rate(version=1, rating=rating)
        for model, field in [(Complete, 'resolution'), (Reason, 'reason')]:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    model(version=1, **{field: ' \n\t '})

    def test_unavailable_directory_never_accepts_demo_identity(self):
        with self.assertRaises(Problem) as raised:
            UnavailableDirectory().authenticate('demo-dispatcher')
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(raised.exception.code, 'IDENTITY_UNAVAILABLE')


class IdempotentProviderDouble:
    """Explicit M1 test double, only persistence of a source receipt, not seats.

    A real M1's source provenance and room availability remain unverified.
    """
    def __init__(self, *, block_first=False):
        self.lock = threading.Lock()
        self.calls = []
        self.receipts = {}
        self.block_first = block_first
        self.applied = threading.Event()
        self.release = threading.Event()

    def put(self, source_id, payload, correlation_id):
        with self.lock:
            self.calls.append((source_id, dict(payload), correlation_id))
            first = len(self.calls) == 1
            key = (source_id, payload['revision'])
            candidate = {**payload, 'sourceSystem': 'M3', 'sourceId': source_id,
                         'appliedAt': '2026-10-26T08:00:01.000000Z'}
            if key in self.receipts:
                if self.receipts[key] != candidate:
                    raise GatewayFailure('M1_HTTP_409', False)
            else:
                self.receipts[key] = candidate
            receipt = dict(self.receipts[key])
        if first:
            self.applied.set()
            if self.block_first and not self.release.wait(5):
                raise RuntimeError('Independent test did not release the delayed provider')
        return receipt


class TransactionAndLeaseReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.url = 'sqlite:///' + str(Path(self.temp.name) / 'review.db')
        self.database = Database(self.url, allow_sqlite=True)
        self.database.migrate()
        # Separate Database instances have separate Python locks. These tests
        # therefore exercise SQLite transactions, not just one process lock.
        self.second_database = Database(self.url, allow_sqlite=True)
        self.directory = DevelopmentDirectory()
        self.now = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)
        self.service = WorkOrders(self.database, self.directory, clock=lambda: self.now)
        self.second_service = WorkOrders(self.second_database, self.directory,
                                         clock=lambda: self.now)
        self.student = self.directory.authenticate('demo-student')
        self.dispatcher = self.directory.authenticate('demo-dispatcher')
        self.technician = self.directory.authenticate('demo-technician')
        self.body = CreateOrder(roomId='room-101', title='Lease review',
                                description='Synthetic repair request.', category='other')

    def tearDown(self):
        self.second_database.close()
        self.database.close()
        self.temp.cleanup()

    def action(self, order, action, actor, **fields):
        return self.service.command(actor, order['id'], action,
                                     {'version': order['version'], **fields})

    def pending_order(self):
        order = self.service.create(self.student, self.body, 'lease-order')
        order = self.action(order, 'assign', self.dispatcher, assigneeId=self.technician.id)
        return self.action(order, 'start', self.technician)

    def job(self, revision):
        with self.database.read() as connection:
            return dict(connection.execute(select(outbox).where(
                outbox.c.revision == revision)).mappings().one())

    def test_late_first_worker_receipt_cannot_repeat_transition_or_reopen_closed_order(self):
        pending = self.pending_order()
        provider = IdempotentProviderDouble(block_first=True)
        first_worker = Worker(self.service, provider, lease_seconds=30)
        second_worker = Worker(self.second_service, provider, lease_seconds=30)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first_result = pool.submit(first_worker.run_once)
            try:
                self.assertTrue(provider.applied.wait(3), 'First request never reached provider')
                original_claim = self.job(1)
                self.assertEqual(original_claim['status'], 'PROCESSING')
                self.now += timedelta(seconds=31)
                self.assertTrue(second_worker.run_once())
                recovered = self.service.get(self.student, pending['id'])
                self.assertEqual(recovered['status'], 'IN_PROGRESS')
                self.assertEqual(provider.calls[0], provider.calls[1])
                # Let the second worker finish a newer source revision before
                # the old ACTIVE response arrives at the first worker.
                completed = self.action(recovered, 'complete', self.technician,
                                        resolution='Synthetic repair completed.')
                accepting = self.action(completed, 'accept', self.student)
                self.assertTrue(second_worker.run_once())
                closed_before_late_receipt = self.service.get(self.student, accepting['id'])
                self.assertEqual(closed_before_late_receipt['status'], 'CLOSED')
            finally:
                provider.release.set()
            self.assertTrue(first_result.result(timeout=3))
        final = self.service.get(self.student, pending['id'])
        self.assertEqual(final, closed_before_late_receipt)
        self.assertEqual(sum(h['action'] == 'M1_ACTIVE_CONFIRMED' for h in final['history']), 1)
        self.assertEqual(sum(h['action'] == 'M1_RELEASE_CONFIRMED' for h in final['history']), 1)
        self.assertEqual(self.job(1)['status'], 'SENT')
        self.assertEqual(self.job(2)['status'], 'SENT')
        self.assertFalse(first_worker.run_once())

    def test_remote_success_followed_by_local_commit_failure_recovers_after_restart(self):
        pending = self.pending_order()
        provider = IdempotentProviderDouble()
        for revision, expected_status, expected_event in [
            (1, 'IN_PROGRESS', 'M1_ACTIVE_CONFIRMED'),
            (2, 'CLOSED', 'M1_RELEASE_CONFIRMED'),
        ]:
            with self.subTest(revision=revision):
                before = self.service.get(self.student, pending['id'])
                call_start = len(provider.calls)
                injected = []

                def fail_receipt_commit(connection):
                    state = connection.execute(select(outbox.c.status).where(
                        outbox.c.order_id == pending['id'],
                        outbox.c.revision == revision)).scalar_one()
                    if state == 'SENT' and not injected:
                        injected.append(True)
                        raise RuntimeError('Injected database commit failure after remote success')

                # Failure injection is at SQLAlchemy's commit boundary. Domain
                # transitions, serialization and outbox processing stay real.
                event.listen(self.database.engine, 'commit', fail_receipt_commit)
                try:
                    with self.assertRaisesRegex(RuntimeError, 'Injected database commit failure'):
                        Worker(self.service, provider).run_once()
                finally:
                    event.remove(self.database.engine, 'commit', fail_receipt_commit)
                self.assertEqual(injected, [True])
                self.assertIn((pending['id'], revision), provider.receipts)
                self.assertEqual(self.service.get(self.student, pending['id']), before)
                failed_transaction = self.job(revision)
                self.assertEqual(failed_transaction['status'], 'PROCESSING')
                self.assertIsNone(failed_transaction['receipt'])

                # New engine/service represent a restarted consumer using the
                # durable database. The provider returns its original receipt.
                self.second_database.close()
                self.second_database = Database(self.url, allow_sqlite=True)
                self.second_database.check_schema()
                self.second_service = WorkOrders(self.second_database, self.directory,
                                                 clock=lambda: self.now)
                recovery = Worker(self.second_service, provider)
                self.assertFalse(recovery.run_once(), 'Unexpired lease was stolen')
                self.now += timedelta(seconds=31)
                self.assertTrue(recovery.run_once())
                after = self.service.get(self.student, pending['id'])
                self.assertEqual(after['status'], expected_status)
                self.assertEqual(after['version'], before['version'] + 1)
                self.assertEqual(sum(h['action'] == expected_event for h in after['history']), 1)
                self.assertEqual(provider.calls[call_start], provider.calls[call_start + 1])
                stored_job = self.job(revision)
                self.assertEqual(stored_job['status'], 'SENT')
                self.assertEqual(json.loads(stored_job['receipt']),
                                 provider.receipts[(pending['id'], revision)])
                self.assertFalse(recovery.run_once())
                if revision == 1:
                    done = self.action(after, 'complete', self.technician, resolution='Fixed.')
                    self.action(done, 'accept', self.student)

    def test_parallel_scanners_with_separate_database_locks_emit_one_event_per_order(self):
        orders = [self.service.create(self.student, self.body, f'scan-{index}')
                  for index in range(3)]
        self.now += timedelta(hours=24)
        barrier = threading.Barrier(8)

        def scan(index):
            barrier.wait(timeout=3)
            service = self.service if index % 2 == 0 else self.second_service
            return service.escalate_due()

        with ThreadPoolExecutor(max_workers=8) as pool:
            counts = list(pool.map(scan, range(8)))
        self.assertEqual(sum(counts), 3)
        self.assertEqual(sorted(counts), [0, 0, 0, 0, 0, 0, 0, 3])
        for original in orders:
            latest = self.service.get(self.student, original['id'])
            self.assertEqual(latest['status'], 'REPORTED')
            self.assertTrue(latest['escalated'])
            self.assertEqual(latest['version'], original['version'] + 1)
            self.assertEqual(sum(h['action'] == 'ESCALATED' for h in latest['history']), 1)

    def test_repeated_ack_commit_failures_exhaust_attempt_budget_before_another_send(self):
        pending = self.pending_order()
        provider = IdempotentProviderDouble()
        worker = Worker(self.service, provider, max_attempts=2)

        def fail_every_ack_commit(connection):
            status = connection.execute(select(outbox.c.status)).scalar_one()
            if status == 'SENT':
                raise RuntimeError('Injected repeated acknowledgement commit failure')

        event.listen(self.database.engine, 'commit', fail_every_ack_commit)
        try:
            for attempt in range(2):
                with self.subTest(attempt=attempt + 1):
                    with self.assertRaisesRegex(RuntimeError, 'Injected repeated acknowledgement'):
                        worker.run_once()
                    self.assertEqual(self.job(1)['attempts'], attempt + 1)
                    self.now += timedelta(seconds=31)
        finally:
            event.remove(self.database.engine, 'commit', fail_every_ack_commit)
        self.assertEqual(len(provider.calls), 2)
        self.assertTrue(worker.run_once())
        self.assertEqual(len(provider.calls), 2, 'Expired leases must not bypass retry budget')
        failed = self.service.get(self.student, pending['id'])
        self.assertEqual((failed['status'], failed['syncStatus']), ('STARTING_REPAIR', 'FAILED'))
        self.assertEqual(self.job(1)['status'], 'FAILED')
        self.assertEqual(self.job(1)['retryable'], 1)
        self.assertFalse(worker.run_once())
        self.action(failed, 'retry-sync', self.dispatcher,
                    reason='Reviewed M1 receipt and recovered database availability.')
        self.assertTrue(worker.run_once())
        self.assertEqual(len(provider.calls), 3)
        self.assertTrue(all(call == provider.calls[0] for call in provider.calls))
        recovered = self.service.get(self.student, pending['id'])
        self.assertEqual(recovered['status'], 'IN_PROGRESS')
        self.assertEqual(sum(h['action'] == 'M1_ACTIVE_CONFIRMED' for h in recovered['history']), 1)


class FormalModeReviewTests(unittest.TestCase):
    def test_configuration_disallows_stubs_and_sqlite_outside_development(self):
        for mode in ['unconfigured', 'production']:
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    Settings(mode=mode, m1_mode='stub')
                with self.assertRaises(ValueError):
                    Settings(mode=mode, database_url='sqlite:///:memory:')
        with self.assertRaises(ValueError):
            Settings(mode='develpoment', m1_mode='stub')

    def test_normal_lifespan_does_not_start_worker_or_enable_demo_identity(self):
        from services.m3.main import create_app

        async def check(mode):
            # Deliberately unreachable PostgreSQL URL: this is a fail-closed
            # lifespan check, not PostgreSQL behavior or connectivity evidence.
            config = Settings(mode=mode,
                database_url='postgresql://unused:unused@127.0.0.1:1/unconfigured',
                m1_mode='http', m1_url='http://127.0.0.1:1', m1_token='synthetic-only')
            app = create_app(config)
            workers_before = {t.ident for t in threading.enumerate() if t.name == 'm3-worker'}
            async with app.router.lifespan_context(app):
                self.assertIsNone(app.state.service)
                self.assertIsInstance(app.state.directory, UnavailableDirectory)
                with self.assertRaises(Problem) as raised:
                    app.state.directory.authenticate('demo-dispatcher')
                self.assertEqual(raised.exception.code, 'IDENTITY_UNAVAILABLE')
                self.assertEqual({t.ident for t in threading.enumerate() if t.name == 'm3-worker'},
                                 workers_before)

        for mode in ['production', 'unconfigured']:
            with self.subTest(mode=mode):
                asyncio.run(check(mode))


if __name__ == '__main__':
    unittest.main()
