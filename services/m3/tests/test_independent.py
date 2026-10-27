"""Independent acceptance checks against real M3 policy, storage and HTTP.

Only the external D directory and M1 server are substitutes. No M3 policy,
database transaction, outbox, receipt validator, or clock calculation is mocked.
M3_TEST_DATABASE_URL must name a disposable database: the fixture clears M3 data.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Event, Lock, Thread
import time

import pytest
from sqlalchemy import delete, inspect, select, text

from services.m3.database import Database, keys, orders, outbox
from services.m3.m1_client import M1Client
from services.m3.ports import Actor
from services.m3.service import DomainError, WorkOrderService, stamp
from services.m3.settings import Settings
from services.m3.worker import Worker


REPORTER = Actor("reporter", "报修人", "reporter")
OTHER = Actor("other", "其他用户", "reporter")
ADMIN = Actor("admin", "管理员", "admin")
TECH = Actor("technician", "维修员一", "technician")
TECH2 = Actor("technician2", "维修员二", "technician")


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


class Directory:
    """Synthetic external D data, including a user whose role can change."""
    def rooms(self, actor):
        return [{"id": "independent-room", "name": "测试自习室"}]

    def technicians(self, actor):
        return [TECH, TECH2, Actor(REPORTER.id, REPORTER.name, "technician")]


@pytest.fixture
def system(tmp_path):
    url = os.getenv("M3_TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'independent.db'}")
    if os.getenv("M3_REQUIRE_POSTGRES") == "1":
        assert url.startswith("postgresql"), "M3_REQUIRE_POSTGRES requires a real PostgreSQL test URL"
    if "M3_TEST_DATABASE_URL" in os.environ:
        assert os.getenv("M3_TEST_ALLOW_RESET") == "1", "Explicit permission to clear the disposable M3 test database is required"
    database = Database(url)
    database.migrate()
    # The environment override is explicitly a disposable test database.
    with database.transaction() as conn:
        for table in (outbox, keys, orders):
            conn.execute(delete(table))
    clock = Clock()
    settings = Settings(mode="test", directory_mode="development", database_url=url,
                        worker_enabled=False, m1_timeout_seconds=0.1)
    service = WorkOrderService(database, Directory(), settings, clock)
    yield service, clock
    database.close()


def create(service, actor=REPORTER, key="independent", **changes):
    payload = {"roomId": "independent-room", "category": "electrical",
               "title": "照明故障", "description": "自习室照明无法正常开启"}
    payload.update(changes)
    return service.create(actor, payload, key)[0]


def act(service, order, action, actor, **payload):
    latest = service.get(order["id"], ADMIN)
    return service.act(order["id"], action, actor, {"version": latest["version"], **payload})


def ready_to_start(service, key="independent", actor=REPORTER, technician=TECH):
    order = create(service, actor=actor, key=key)
    return act(service, order, "assign", ADMIN, assigneeId=technician.id)


class HttpPeer:
    """Test-only network peer; persists source snapshots without M1 internals."""
    def __init__(self):
        self.requests = []
        self.states = {}
        self.responses = []
        self.lock = Lock()
        self.entered = Event()
        self.release = Event()
        self.delay = 0

    def reply(self, handler):
        payload = json.loads(handler.rfile.read(int(handler.headers["Content-Length"])))
        source = handler.path.rsplit("/", 1)[-1]
        record = {"source": source, "path": handler.path, "payload": payload,
                  "authorization": handler.headers.get("Authorization"),
                  "correlation": handler.headers.get("X-Correlation-Id")}
        with self.lock:
            self.requests.append(record)
            response = self.responses.pop(0) if self.responses else None
        self.entered.set()
        if self.delay:
            time.sleep(self.delay)
        body = {"sourceSystem": "M3", "sourceId": source, **payload,
                "appliedAt": "2026-10-27T00:00:01Z"}
        status = 200
        if isinstance(response, int):
            status, body = response, {"error": "synthetic upstream error"}
        elif callable(response):
            body = response(body)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        if status == 200 and isinstance(body, dict) and body.get("sourceId") == source:
            with self.lock:
                self.states[source] = deepcopy(body)
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        try:
            handler.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected when exercising the real client's timeout.


@contextmanager
def peer_server():
    peer = HttpPeer()

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self):
            peer.reply(self)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    peer.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield peer
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def worker_for(service, peer):
    return Worker(service, M1Client(peer.url, "independent-service-token", timeout=0.1))


def test_reassignment_revokes_previous_worker_without_extending_sla(system):
    service, clock = system
    order = ready_to_start(service)
    due = order["dueAt"]
    clock.advance(hours=12)
    reassigned = act(service, order, "assign", ADMIN, assigneeId=TECH2.id)
    assert reassigned["dueAt"] == due
    assert service.list(TECH) == []
    with pytest.raises(DomainError) as denied:
        service.act(order["id"], "start", TECH, {"version": reassigned["version"]})
    assert denied.value.status == 404
    started = act(service, order, "start", TECH2)
    assert started["status"] == "BLOCK_PENDING"
    assert started["dueAt"] == due


def test_previous_repairer_cannot_accept_after_reassignment_and_role_change(system):
    service, _ = system
    reporter_technician = Actor(REPORTER.id, REPORTER.name, "technician")
    order = ready_to_start(service, technician=reporter_technician)
    act(service, order, "start", reporter_technician)
    with peer_server() as peer:
        assert worker_for(service, peer).run_once()
    act(service, order, "assign", ADMIN, assigneeId=TECH2.id)
    act(service, order, "complete", TECH2, note="已更换灯具")
    for actor in (REPORTER, Actor(REPORTER.id, REPORTER.name, "admin")):
        latest = service.get(order["id"], actor)
        assert "accept" not in latest["allowedActions"]
        assert "reject" not in latest["allowedActions"]
        for action in ("accept", "reject"):
            with pytest.raises(DomainError) as denied:
                service.act(order["id"], action, actor,
                            {"version": latest["version"], "note": "验收说明"})
            assert denied.value.status == 403


def test_object_authorization_idempotency_and_stale_version(system):
    service, _ = system
    order = create(service)
    assert create(service)["id"] == order["id"]
    with pytest.raises(DomainError) as conflict:
        create(service, title="不同报修")
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
    assert create(service, actor=OTHER)["id"] != order["id"]
    assert all(item["reporterId"] == OTHER.id for item in service.list(OTHER))
    with pytest.raises(DomainError) as hidden:
        service.get(order["id"], OTHER)
    assert hidden.value.status == 404
    with pytest.raises(DomainError) as forbidden:
        service.act(order["id"], "assign", REPORTER,
                    {"version": order["version"], "assigneeId": TECH.id})
    assert forbidden.value.status == 403
    act(service, order, "assign", ADMIN, assigneeId=TECH.id)
    with pytest.raises(DomainError) as stale:
        service.act(order["id"], "cancel", REPORTER,
                    {"version": order["version"], "note": "不再需要维修"})
    assert stale.value.code == "VERSION_CONFLICT"


def test_concurrent_creation_and_sla_scans_are_idempotent_at_exact_boundary(system):
    service, clock = system
    with ThreadPoolExecutor(max_workers=6) as pool:
        created = list(pool.map(lambda _: create(service), range(12)))
    assert len({order["id"] for order in created}) == 1
    order = created[0]
    clock.advance(hours=24, microseconds=-1)
    assert service.scan_sla() == 0
    clock.advance(microseconds=1)
    with ThreadPoolExecutor(max_workers=6) as pool:
        counts = list(pool.map(lambda _: service.scan_sla(), range(12)))
    assert sum(counts) == 1
    latest = service.get(order["id"], ADMIN)
    assert latest["escalated"] is True
    assert sum(event["action"] == "sla-escalated" for event in latest["history"]) == 1
    assert [item["id"] for item in service.list(ADMIN, view="overdue")] == [order["id"]]


def test_same_room_sources_are_independent_and_acceptance_waits_for_receipt(system):
    service, _ = system
    first = ready_to_start(service, key="first")
    second = ready_to_start(service, key="second")
    for order in (first, second):
        act(service, order, "start", TECH)
    with peer_server() as peer:
        worker = worker_for(service, peer)
        assert worker.run_once() and worker.run_once()
        assert set(peer.states) == {first["id"], second["id"]}
        act(service, first, "complete", TECH, note="修复完成")
        assert peer.states[first["id"]]["status"] == "ACTIVE"
        accepted = act(service, first, "accept", REPORTER)
        assert accepted["status"] == "RELEASE_PENDING"
        assert peer.states[first["id"]]["status"] == "ACTIVE"
        assert worker.run_once()
        assert service.get(first["id"], ADMIN)["status"] == "CLOSED"
        assert peer.states[first["id"]]["status"] == "RELEASED"
        assert peer.states[first["id"]]["revision"] == 2
        assert peer.states[second["id"]]["status"] == "ACTIVE"
        assert all(x["authorization"] == "Bearer independent-service-token" for x in peer.requests)
        assert all(x["path"] == f"/internal/v1/room-blocks/m3/{x['source']}" for x in peer.requests)


@pytest.mark.parametrize("corruption", [
    lambda body: {**body, "sourceSystem": "M2"},
    lambda body: {**body, "sourceId": "another-work-order"},
    lambda body: {**body, "roomId": "another-room"},
    lambda body: {**body, "revision": True},
    lambda body: {**body, "revision": 2},
    lambda body: {**body, "status": "RELEASED"},
    lambda body: {**body, "startsAt": "2026-10-27T00:00:00+00:00"},
    lambda body: {**body, "appliedAt": "2026-02-30T00:00:00Z"},
    lambda body: {**body, "appliedAt": "2026-10-27T00:00:01+00:00"},
    lambda body: {**body, "unexpected": "field"},
    lambda body: {key: value for key, value in body.items() if key != "appliedAt"},
    lambda body: None,
    lambda body: b'{"sourceId":"first","sourceId":"second"}',
], ids=["wrong-system", "wrong-source", "wrong-room", "bool-version", "wrong-version",
        "wrong-state", "offset-start", "invalid-date", "offset-applied", "extra-field",
        "missing-applied", "null-body", "duplicate-json-key"])
def test_invalid_http_receipt_cannot_advance_work_order(system, corruption):
    service, _ = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        peer.responses = [corruption]
        worker = worker_for(service, peer)
        assert worker.run_once()
        assert not worker.run_once()
        assert len(peer.requests) == 1
    latest = service.get(order["id"], ADMIN)
    assert latest["status"] == "BLOCK_PENDING"
    assert latest["sync"]["status"] == "failed"
    assert latest["sync"]["retryable"] is False
    assert "retry-sync" not in latest["allowedActions"]


def test_retry_budget_backoff_and_explicit_retry_preserve_entire_http_request(system):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        peer.responses = [503] * 5
        worker = worker_for(service, peer)
        for index, delay in enumerate((1, 5, 30, 120, 0)):
            assert worker.run_once()
            assert not worker.run_once()
            latest = service.get(order["id"], ADMIN)
            assert latest["sync"]["attempts"] == index + 1
            clock.advance(seconds=delay)
        failed = service.get(order["id"], ADMIN)
        assert failed["status"] == "BLOCK_PENDING"
        assert failed["sync"]["status"] == "failed"
        assert "retry-sync" in failed["allowedActions"]
        act(service, order, "retry-sync", ADMIN)
        assert worker.run_once()
        assert len(peer.requests) == 6
        assert all(request == peer.requests[0] for request in peer.requests)
        assert service.get(order["id"], ADMIN)["status"] == "IN_PROGRESS"


def test_concurrent_workers_claim_once_and_stale_lease_cannot_settle(system):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        workers = [worker_for(service, peer) for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda worker: worker.claim(), workers))
        claimed = [job for job in claims if job]
        assert len(claimed) == 1
        old = claimed[0]
        assert old["attempts"] == 1
        # Simulate termination after durable claim, before HTTP or settlement.
        clock.value = datetime.fromtimestamp(old["lease_until"], timezone.utc)
        recovered = workers[1].claim()
        assert recovered["attempts"] == 2
        assert recovered["lease_token"] != old["lease_token"]
        assert workers[0].settle(old) is False
        assert service.get(order["id"], ADMIN)["status"] == "BLOCK_PENDING"
        workers[1].client.apply(recovered["order_id"], recovered["payload"], recovered["correlation_id"])
        assert workers[1].settle(recovered) is True
        assert service.get(order["id"], ADMIN)["status"] == "IN_PROGRESS"
        assert len(peer.requests) == 1


def test_repeated_worker_crashes_exhaust_budget_without_unbounded_retry(system):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        for attempt in range(1, 6):
            fresh_worker = worker_for(service, peer)
            claim = fresh_worker.claim()
            assert claim["attempts"] == attempt
            clock.value = datetime.fromtimestamp(claim["lease_until"], timezone.utc)
        assert worker_for(service, peer).claim() is None
        assert peer.requests == []
    latest = service.get(order["id"], ADMIN)
    assert latest["sync"]["status"] == "failed"
    assert latest["sync"]["attempts"] == 5
    assert "retry-sync" in latest["allowedActions"]


def test_network_timeout_remains_pending_and_stops_before_five_retries(system):
    service, _ = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        peer.delay = 0.3
        assert worker_for(service, peer).run_once()
    latest = service.get(order["id"], ADMIN)
    assert latest["status"] == "BLOCK_PENDING"
    assert latest["sync"]["status"] == "pending"
    assert latest["sync"]["retryable"] is True
    assert latest["sync"]["attempts"] == 1


def test_rework_creates_new_sla_stage_and_waiting_for_acceptance_stops_clock(system):
    service, clock = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    with peer_server() as peer:
        assert worker_for(service, peer).run_once()
    clock.advance(hours=48)
    assert service.scan_sla() == 1
    finished = act(service, order, "complete", TECH, note="初次完成")
    assert finished["dueAt"] is None
    clock.advance(days=3)
    assert service.scan_sla() == 0
    rejected = act(service, order, "reject", REPORTER, note="照明仍然闪烁")
    assert rejected["status"] == "IN_PROGRESS"
    assert stamp(rejected["dueAt"]) == clock() + timedelta(hours=48)
    assert rejected["escalated"] is False
    clock.advance(hours=48)
    assert service.scan_sla() == 1
    assert service.scan_sla() == 0
    latest = service.get(order["id"], ADMIN)
    assert sum(x["action"] == "sla-escalated" for x in latest["history"]) == 2


def test_migration_replay_and_restart_preserve_private_schema_and_work(system):
    service, _ = system
    order = ready_to_start(service)
    act(service, order, "start", TECH)
    original_url = service.settings.database_url
    service.db.close()
    restarted = Database(original_url)
    try:
        restarted.migrate()
        restarted.migrate()
        rebuilt = WorkOrderService(restarted, service.directory, service.settings, service.clock)
        assert rebuilt.get(order["id"], ADMIN)["status"] == "BLOCK_PENDING"
        with restarted.transaction() as conn:
            assert conn.execute(select(outbox.c.id)).all()
            schema = "m3" if conn.dialect.name == "postgresql" else None
            assert conn.execute(text(f"SELECT version_num FROM {'m3.' if schema else ''}alembic_version")).scalar_one() == "0001"
            table_names = inspect(conn).get_table_names(schema=schema)
            assert {"work_orders", "outbox", "idempotency_keys", "transaction_guard"} <= set(table_names)
            if schema:
                assert not {"work_orders", "outbox", "idempotency_keys", "transaction_guard"} & set(inspect(conn).get_table_names(schema="public"))
        with peer_server() as peer:
            assert worker_for(rebuilt, peer).run_once()
        assert rebuilt.get(order["id"], ADMIN)["status"] == "IN_PROGRESS"
    finally:
        restarted.close()


@pytest.mark.parametrize("overrides", [
    {"directory_mode": "development"},
    {"m1_mode": "development-http"},
    {"database_url": "sqlite:///demo.db"},
])
def test_production_configuration_rejects_development_dependencies(overrides):
    with pytest.raises(ValueError):
        Settings(mode="production", **overrides)
