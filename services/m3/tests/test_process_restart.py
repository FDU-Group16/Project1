"""Process-level durability and real-HTTP error classification acceptance tests.

The imported fixture uses SQLite by default or the explicitly disposable CI
PostgreSQL database. Children receive its URL through stdin, never command-line
arguments or diagnostic output. Only the external directory/M1 peer are fixtures.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select

from services.m3.database import outbox
from services.m3.service import DomainError
from services.m3.tests.test_independent import (
    ADMIN, TECH, act, peer_server, ready_to_start, system, worker_for,
)


CHILD_PROGRAM = r"""
import json
import os
import sys
from datetime import datetime, timezone
from services.m3.database import Database
from services.m3.m1_client import M1Client
from services.m3.service import WorkOrderService
from services.m3.settings import Settings
from services.m3.worker import Worker
from services.m3.tests.test_independent import Directory

try:
    config = json.load(sys.stdin)
    database = Database(config['database_url'])
    instant = datetime.fromtimestamp(config['now'], timezone.utc)
    settings = Settings(mode='test', directory_mode='development',
        database_url=config['database_url'], worker_enabled=False,
        m1_timeout_seconds=1)
    service = WorkOrderService(database, Directory(), settings, lambda: instant)
    worker = Worker(service, M1Client(config['peer_url'], 'independent-service-token', timeout=1))
    if config['mode'] == 'crash-after-claim':
        claimed = worker.claim()
        if claimed is None:
            raise RuntimeError('No pending delivery')
        print(json.dumps({'pid': os.getpid(), 'claimed': True}), flush=True)
        # Deliberate abnormal termination: no settlement, close(), or finally.
        # The real claim transaction has committed before the process exits.
        os._exit(73)
    processed = worker.run_once()
    database.close()
    print(json.dumps({'pid': os.getpid(), 'processed': processed}), flush=True)
except Exception as error:
    # Do not disclose connection URLs, credentials, or database driver messages.
    print(json.dumps({'failureType': type(error).__name__}), flush=True)
    os._exit(74)
"""


def child(service, peer, now, mode):
    config = {"database_url": service.settings.database_url, "peer_url": peer.url,
              "now": now.timestamp(), "mode": mode}
    result = subprocess.run(
        [sys.executable, "-c", CHILD_PROGRAM],
        cwd=Path(__file__).resolve().parents[3],
        input=json.dumps(config), text=True, capture_output=True, timeout=15,
    )
    # Avoid echoing child input or driver diagnostics on an assertion failure.
    try:
        diagnostic = json.loads(result.stdout.strip())
    except (ValueError, TypeError):
        pytest.fail(f"Child emitted no structured diagnostic (exit {result.returncode})", pytrace=False)
    return result.returncode, diagnostic


def job_for(service, order_id):
    with service.db.transaction() as connection:
        return dict(connection.execute(select(outbox).where(outbox.c.order_id == order_id)).mappings().one())


def test_abnormal_process_exit_after_durable_claim_recovers_in_new_process(system):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    original = job_for(service, order["id"])
    assert original["status"] == "pending" and original["attempts"] == 0

    with peer_server() as peer:
        code, crashed = child(service, peer, clock(), "crash-after-claim")
        assert code == 73 and crashed["claimed"] is True
        assert crashed["pid"] != os.getpid()
        durable = job_for(service, order["id"])
        assert durable["status"] == "processing" and durable["attempts"] == 1
        assert durable["lease_token"] and durable["lease_until"] > clock().timestamp()
        assert durable["correlation_id"] == original["correlation_id"]
        assert durable["payload"] == original["payload"]
        assert service.get(order["id"], ADMIN)["status"] == "BLOCK_PENDING"
        assert peer.requests == []

        code, before_expiry = child(service, peer, clock(), "recover")
        assert code == 0 and before_expiry["processed"] is False
        assert job_for(service, order["id"])["attempts"] == 1
        assert peer.requests == []

        clock.value = datetime.fromtimestamp(durable["lease_until"], timezone.utc)
        code, recovered = child(service, peer, clock(), "recover")
        assert code == 0 and recovered["processed"] is True
        assert recovered["pid"] not in {os.getpid(), crashed["pid"], before_expiry["pid"]}
        assert len(peer.requests) == 1
        request = peer.requests[0]
        assert request["source"] == original["order_id"] == order["id"]
        assert request["payload"] == original["payload"]
        assert request["payload"]["revision"] == 1
        assert request["correlation"] == original["correlation_id"]
        assert request["authorization"] == "Bearer independent-service-token"

    settled = job_for(service, order["id"])
    assert settled["status"] == "succeeded" and settled["attempts"] == 2
    assert settled["payload"] == original["payload"]
    assert settled["correlation_id"] == original["correlation_id"]
    assert settled["lease_token"] is None and settled["lease_until"] is None
    current = service.get(order["id"], ADMIN)
    assert current["status"] == "IN_PROGRESS"
    assert current["sync"]["status"] == "succeeded"
    assert sum(item["action"] == "block-confirmed" for item in current["history"]) == 1


@pytest.mark.parametrize("upstream_status,retryable", [
    (502, True), (504, True),
    (400, False), (401, False), (403, False), (404, False),
    (409, False), (422, False), (500, False), (302, False),
])
def test_real_http_status_controls_retry_without_premature_state_transition(system, upstream_status, retryable):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        peer.responses = [upstream_status]
        worker = worker_for(service, peer)
        assert worker.run_once()
        current = service.get(order["id"], ADMIN)
        assert current["status"] == "BLOCK_PENDING"
        assert current["sync"]["retryable"] is retryable
        assert current["sync"]["status"] == ("pending" if retryable else "failed")
        assert current["sync"]["attempts"] == 1
        assert str(upstream_status) in current["sync"]["error"]
        assert not worker.run_once()
        assert len(peer.requests) == 1
        clock.advance(seconds=1)
        if retryable:
            assert worker.run_once()
            assert len(peer.requests) == 2
            assert peer.requests[1] == peer.requests[0]
            current = service.get(order["id"], ADMIN)
            assert current["status"] == "IN_PROGRESS"
            assert current["sync"]["attempts"] == 2
        else:
            assert not worker.run_once()
            assert len(peer.requests) == 1
            current = service.get(order["id"], ADMIN)
            assert "retry-sync" not in current["allowedActions"]
            with pytest.raises(DomainError) as denied:
                act(service, order, "retry-sync", ADMIN)
            assert denied.value.status == 409
