"""Durable leased HTTP delivery. A claim consumes an attempt before network I/O."""
from threading import Event, Thread
import logging
from uuid import uuid4
from sqlalchemy import select, update
from .database import outbox
from .m1_client import SyncFailure

logger = logging.getLogger(__name__)
RETRY_DELAYS = (1, 5, 30, 120)
MAX_ATTEMPTS = 5


class Worker:
    def __init__(self, service, client):
        self.service, self.client = service, client
        self.stop_event, self.thread = Event(), None

    def _sync(self, connection, job, status, error=None, retryable=True, now=None):
        order = self.service.load(connection, job["order_id"])
        if order["_jobId"] != job["id"]:
            return
        order["sync"] = {"status": status, "attempts": job["attempts"],
                         "error": error, "retryable": retryable}
        if status == "succeeded":
            expected = "BLOCK_PENDING" if job["payload"]["status"] == "ACTIVE" else "RELEASE_PENDING"
            if order["status"] != expected:
                raise RuntimeError("Outbox and work order state diverged")
            order["status"] = "IN_PROGRESS" if expected == "BLOCK_PENDING" else "CLOSED"
            self.service.history(order, "block-confirmed" if expected == "BLOCK_PENDING" else "release-confirmed", now=now)
        elif status == "failed":
            self.service.history(order, "sync-failed", note=error or "写回失败", now=now)
        self.service.save(connection, order, now)

    def claim(self):
        now = self.service.clock()
        with self.service.db.transaction() as connection:
            jobs = connection.execute(select(outbox).where(outbox.c.status.in_(["pending", "processing"]))
                                      .order_by(outbox.c.next_attempt, outbox.c.id)).mappings().all()
            for original in jobs:
                job = dict(original)
                if job["status"] == "pending" and job["next_attempt"] > now.timestamp():
                    continue
                if job["status"] == "processing" and job["lease_until"] and job["lease_until"] > now.timestamp():
                    continue
                if job["attempts"] >= MAX_ATTEMPTS:
                    error = "自动尝试次数已耗尽，请管理员核对依赖后重试"
                    connection.execute(update(outbox).where(outbox.c.id == job["id"]).values(
                        status="failed", error=error, retryable=1, lease_until=None, lease_token=None))
                    self._sync(connection, job, "failed", error, True, now)
                    continue
                job.update(status="processing", attempts=job["attempts"] + 1,
                           lease_token=str(uuid4()), lease_until=now.timestamp() + max(30, self.service.settings.m1_timeout_seconds * 2 + 5))
                connection.execute(update(outbox).where(outbox.c.id == job["id"]).values(
                    status=job["status"], attempts=job["attempts"], lease_token=job["lease_token"], lease_until=job["lease_until"]))
                self._sync(connection, job, "processing", now=now)
                return job
        return None

    def settle(self, claimed, failure=None):
        now = self.service.clock()
        with self.service.db.transaction() as connection:
            row = connection.execute(select(outbox).where(outbox.c.id == claimed["id"])).mappings().one()
            job = dict(row)
            if job["lease_token"] != claimed["lease_token"] or job["status"] != "processing":
                return False
            retryable = failure.retryable if failure else False
            status = "succeeded" if failure is None else (
                "pending" if retryable and job["attempts"] < MAX_ATTEMPTS else "failed")
            error = failure.message if failure else None
            next_attempt = now.timestamp() + RETRY_DELAYS[job["attempts"] - 1] if status == "pending" else now.timestamp()
            connection.execute(update(outbox).where(outbox.c.id == job["id"]).values(
                status=status, next_attempt=next_attempt, lease_until=None, lease_token=None,
                error=error, retryable=int(retryable)))
            self._sync(connection, job, status, error, retryable, now)
        return True

    def run_once(self):
        self.service.scan_sla()
        job = self.claim()
        if not job:
            return False
        try:
            self.client.apply(job["order_id"], job["payload"], job["correlation_id"])
        except SyncFailure as failure:
            self.settle(job, failure)
        else:
            self.settle(job)
        return True

    def _loop(self):
        while not self.stop_event.is_set():
            try:
                processed = self.run_once()
            except Exception:
                # Do not emit request bodies, credentials, database URLs, or tracebacks.
                logger.error("M3 worker iteration failed; durable lease will recover")
                processed = False
            self.stop_event.wait(0.05 if processed else self.service.settings.worker_interval_seconds)

    def start(self):
        self.stop_event.clear()
        self.thread = Thread(target=self._loop, daemon=True, name="m3-outbox")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=self.service.settings.m1_timeout_seconds + 2)
