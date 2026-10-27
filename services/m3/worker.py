"""Persisted M1 retries and SLA scanning. Network I/O never holds a DB lock."""

import json
import logging
from datetime import timedelta
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import select, update

from .m1_client import validate_receipt
from .migrations.v0001 import outbox
from .models import timestamp
from .ports import BlockGateway, GatewayFailure
from .service import WorkOrders

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, service: WorkOrders, gateway: BlockGateway, *, interval=2.0,
                 max_attempts=5, lease_seconds=30):
        self.service, self.gateway = service, gateway
        self.interval, self.max_attempts, self.lease_seconds = interval, max_attempts, lease_seconds
        self.stop_event = Event()
        self.thread = None

    def run_once(self) -> bool:
        with self.service.database.transaction() as connection:
            now_dt = self.service.clock()
            now = timestamp(now_dt)
            job = connection.execute(select(outbox).where(
                outbox.c.status.in_(['PENDING', 'PROCESSING']),
                outbox.c.next_attempt_at <= now).order_by(outbox.c.next_attempt_at, outbox.c.id)
                .limit(1)).mappings().first()
            if not job:
                return False
            job = dict(job)
            if job['attempts'] >= self.max_attempts:
                # A worker may have died after its final send, before persisting
                # the result. Preserve the same payload for deliberate recovery,
                # but do not turn crash recovery into unbounded automatic sends.
                connection.execute(update(outbox).where(outbox.c.id == job['id']).values(
                    status='FAILED', lease_id=None, retryable=1,
                    last_error='M1_NETWORK_UNAVAILABLE'))
                order = self.service._get(connection, job['order_id'])
                order['syncStatus'], order['syncError'] = 'FAILED', 'M1_NETWORK_UNAVAILABLE'
                self.service.event(order, 'SYNC_FAILED', 'system', now,
                    '最后一次写回结果未能确认；自动重试已耗尽，需核对后重试相同请求。')
                self.service.save(connection, order)
                return True
            lease_id = str(uuid4())
            attempts = job['attempts'] + 1
            connection.execute(update(outbox).where(outbox.c.id == job['id']).values(
                status='PROCESSING', attempts=attempts, lease_id=lease_id,
                next_attempt_at=timestamp(now_dt + timedelta(seconds=self.lease_seconds))))
        failure = None
        receipt = None
        payload = json.loads(job['payload'])
        try:
            receipt = self.gateway.put(job['order_id'], payload, job['correlation_id'])
            validate_receipt(job['order_id'], payload, receipt)
        except GatewayFailure as exc:
            failure = exc
        except Exception:
            # Unknown adapter bugs must not be interpreted as a successful write.
            failure = GatewayFailure('M1_ADAPTER_ERROR', False)
            logger.error('M3 writeback adapter failed unexpectedly')
        with self.service.database.transaction() as connection:
            current = connection.execute(select(outbox).where(outbox.c.id == job['id'])).mappings().one()
            # An expired claim may have been recovered by another worker. Only
            # the current lease may append an acknowledgement or alter status.
            if current['status'] != 'PROCESSING' or current['lease_id'] != lease_id:
                return True
            now_dt = self.service.clock()
            now = timestamp(now_dt)
            order = self.service._get(connection, job['order_id'])
            if failure:
                exhausted = attempts >= self.max_attempts
                terminal = exhausted or not failure.retryable
                connection.execute(update(outbox).where(outbox.c.id == job['id']).values(
                    status='FAILED' if terminal else 'PENDING', last_error=failure.code,
                    retryable=int(failure.retryable), lease_id=None,
                    next_attempt_at=timestamp(now_dt + timedelta(seconds=min(5 * 2 ** (attempts - 1), 60)))))
                order['syncStatus'] = 'FAILED' if terminal else 'PENDING'
                order['syncError'] = failure.code
                self.service.event(order, 'SYNC_FAILED' if terminal else 'SYNC_RETRY_SCHEDULED',
                    'system', now, f'M1 同步失败：{failure.code}；尝试 {attempts}/{self.max_attempts}。')
            else:
                expected_state = 'STARTING_REPAIR' if payload['status'] == 'ACTIVE' else 'ACCEPTING'
                if order['status'] != expected_state or order['_blockRevision'] != payload['revision']:
                    raise RuntimeError('M3 outbox and work-order state diverged; reconciliation required')
                connection.execute(update(outbox).where(outbox.c.id == job['id']).values(
                    status='SENT', lease_id=None, receipt=json.dumps(receipt), last_error=None))
                order['status'] = 'IN_PROGRESS' if payload['status'] == 'ACTIVE' else 'CLOSED'
                order['syncStatus'], order['syncError'] = 'SYNCED', None
                if order['status'] == 'CLOSED':
                    order['dueAt'] = None
                self.service.event(order, 'M1_ACTIVE_CONFIRMED' if payload['status'] == 'ACTIVE'
                    else 'M1_RELEASE_CONFIRMED', 'system', now,
                    '已确认本工单来源的 M1 回执；其他来源限制由 M1 保留。')
            self.service.save(connection, order)
        return True

    def tick(self):
        self.service.escalate_due()
        for _ in range(10):
            if self.stop_event.is_set() or not self.run_once():
                break

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception as exc:
                # Keep running after transient DB failures without leaking SQL,
                # credentials, or report descriptions into logs.
                logger.error('M3 worker tick failed (%s); will retry', type(exc).__name__)
            self.stop_event.wait(self.interval)

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Worker already started')
        self.thread = Thread(target=self._loop, name='m3-worker', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError('M3 worker did not stop within shutdown deadline')
