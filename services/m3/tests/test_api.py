"""Behavioral API tests run unchanged against SQLite or the dedicated CI PostgreSQL."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, inspect, text
from sqlalchemy.engine import make_url
from services.m3.database import Database, keys, orders, outbox
from services.m3.main import create_app
from services.m3.m1_client import M1Client, SyncFailure
from services.m3.settings import Settings
from services.m3.seed import seed
from services.m3.service import WorkOrderService

BASE = "/api/m3/v1"
PAYLOAD = {"roomId": "room-101", "category": "electrical", "title": "灯具损坏", "description": "靠窗的灯无法点亮"}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 27, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def auth(token="demo-reporter", **headers):
    return {"Authorization": f"Bearer {token}", **headers}


@pytest.fixture
def environment(tmp_path):
    url = os.getenv("M3_TEST_DATABASE_URL")
    if os.getenv("M3_REQUIRE_POSTGRES") == "1" and not url:
        pytest.fail("M3_REQUIRE_POSTGRES requires M3_TEST_DATABASE_URL")
    if url:
        assert url.startswith("postgresql"), "CI test URL must be PostgreSQL"
        assert os.getenv("M3_TEST_ALLOW_RESET") == "1", "Dedicated test database reset must be explicit"
        assert "test" in (make_url(url).database or "").lower(), "Refuse to reset a non-test database"
    else:
        url = f"sqlite:///{tmp_path}/orders.sqlite3"
    db = Database(url)
    db.migrate()
    with db.transaction() as connection:
        connection.execute(delete(keys))
        connection.execute(delete(outbox))
        connection.execute(delete(orders))
    clock = Clock()
    requests = []

    def receive(request):
        payload = json.loads(request.content)
        requests.append((request.url.path, payload, request.headers["x-correlation-id"]))
        return httpx.Response(200, json={"sourceSystem": "M3", "sourceId": request.url.path.rsplit("/", 1)[-1],
                              **payload, "appliedAt": "2026-10-27T00:00:00Z"})

    client = M1Client("http://fixture.invalid", "synthetic-service", transport=httpx.MockTransport(receive))
    settings = Settings(mode="test", directory_mode="development", database_url=url, worker_enabled=False)
    app = create_app(settings, db=db, clock=clock, m1_client=client)
    with TestClient(app) as api:
        yield api, app, clock, requests
    db.close()


def create(api, key="create-1", token="demo-reporter", payload=None):
    return api.post(BASE + "/work-orders", json=payload or PAYLOAD,
                    headers=auth(token, **{"Idempotency-Key": key}))


def get(api, order, token="demo-reporter"):
    result = api.get(BASE + "/work-orders/" + order["id"], headers=auth(token))
    assert result.status_code == 200, result.text
    return result.json()


def action(api, order, name, token="demo-reporter", **payload):
    return api.post(f"{BASE}/work-orders/{order['id']}/{name}",
                    headers=auth(token), json={"version": order["version"], **payload})


def progressing(api, app):
    order = create(api).json()
    result = action(api, order, "assign", "demo-admin", assigneeId="technician-1")
    assert result.status_code == 200, result.text
    order = result.json()
    result = action(api, order, "start", "demo-technician")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "BLOCK_PENDING"
    app.state.worker.run_once()
    return get(api, order)


def test_full_lifecycle_waits_for_receipts_and_rates_once(environment):
    api, app, _, requests = environment
    order = progressing(api, app)
    assert order["status"] == "IN_PROGRESS"
    order = action(api, order, "complete", "demo-technician", note="已更换灯具并测试").json()
    assert order["status"] == "PENDING_ACCEPTANCE"
    assert len(requests) == 1 and order["dueAt"] is None
    order = action(api, order, "accept").json()
    assert order["status"] == "RELEASE_PENDING"
    assert action(api, order, "rate", score=5).status_code == 409
    app.state.worker.run_once()
    order = get(api, order)
    assert order["status"] == "CLOSED"
    assert [r[1]["status"] for r in requests] == ["ACTIVE", "RELEASED"]
    assert requests[0][0] == requests[1][0]
    order = action(api, order, "rate", score=5, comment="修好了").json()
    assert order["rating"]["score"] == 5
    assert action(api, order, "rate", score=3).status_code == 409


def test_rejection_keeps_block_and_starts_new_sla(environment):
    api, app, clock, requests = environment
    order = progressing(api, app)
    order = action(api, order, "complete", "demo-technician", note="已处理").json()
    clock.now += timedelta(hours=60)
    assert app.state.service.scan_sla() == 0
    order = action(api, order, "reject", note="仍然闪烁").json()
    assert order["status"] == "IN_PROGRESS" and len(requests) == 1
    assert order["dueAt"] == (clock.now + timedelta(hours=48)).isoformat().replace("+00:00", "Z")
    clock.now += timedelta(hours=48)
    assert app.state.service.scan_sla() == 1
    assert app.state.service.scan_sla() == 0


def test_admin_acceptance_requires_reason(environment):
    api, app, _, _ = environment
    order = progressing(api, app)
    order = action(api, order, "complete", "demo-technician", note="已修复").json()
    assert action(api, order, "accept", "demo-admin").status_code == 422
    result = action(api, order, "accept", "demo-admin", note="报修人委托，现场核验已完成")
    assert result.status_code == 200


def test_permission_and_visibility_precede_filters(environment):
    api, _, _, _ = environment
    order = create(api).json()
    assert api.get(BASE + "/work-orders/" + order["id"], headers=auth("demo-reporter-2")).status_code == 404
    assert api.get(BASE + "/work-orders?view=all&q=灯", headers=auth("demo-reporter-2")).json() == {"items": []}
    assert action(api, order, "assign", assigneeId="technician-1").status_code == 403
    assert api.get(BASE + "/technicians", headers=auth()).status_code == 403
    assert api.get(BASE + "/me").status_code == 401
    assert api.get(BASE + "/me", headers=auth("invalid")).status_code == 401


def test_idempotency_scoped_by_actor_and_conflicts(environment):
    api, _, _, _ = environment
    first = create(api)
    duplicate = create(api)
    assert first.status_code == 201 and duplicate.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]
    assert create(api, payload={**PAYLOAD, "title": "其他故障"}).status_code == 409
    assert create(api, token="demo-reporter-2").status_code == 201


def test_version_conflict_and_cancellation_boundary(environment):
    api, app, _, _ = environment
    order = create(api).json()
    assigned = action(api, order, "assign", "demo-admin", assigneeId="technician-1").json()
    assert action(api, order, "cancel", note="撤回").status_code == 409
    pending = action(api, assigned, "start", "demo-technician").json()
    assert action(api, pending, "cancel", note="撤回").status_code == 409
    app.state.worker.run_once()
    assert action(api, get(api, pending), "cancel", note="撤回").status_code == 409
    other = create(api, key="another").json()
    cancelled = action(api, other, "cancel", note="重复报修").json()
    assert cancelled["status"] == "CANCELLED" and cancelled["sync"] is None


@pytest.mark.parametrize("change", [
    {"title": "  "}, {"title": "长" * 121}, {"description": " "}, {"category": "invalid"},
    {"roomId": "absent"}, {"reporterId": "forged"}, {"title": 123}, {"description": "字" * 4001},
])
def test_strict_create_validation(environment, change):
    api, _, _, _ = environment
    assert create(api, payload={**PAYLOAD, **change}).status_code == 422


@pytest.mark.parametrize("payload", [
    {"version": True, "note": "reason"}, {"version": "1", "note": "reason"},
    {"version": 1, "note": "  "}, {"version": 1, "note": "a", "role": "admin"},
])
def test_strict_action_validation(environment, payload):
    api, _, _, _ = environment
    order = create(api).json()
    result = api.post(f"{BASE}/work-orders/{order['id']}/cancel", headers=auth(), json=payload)
    assert result.status_code == 422


def test_migrations_replay_without_losing_data(environment):
    api, app, _, _ = environment
    order = create(api).json()
    app.state.db.migrate()
    assert get(api, order)["title"] == PAYLOAD["title"]
    schema = "m3" if app.state.db.engine.dialect.name == "postgresql" else None
    tables = inspect(app.state.db.engine).get_table_names(schema=schema)
    assert {"work_orders", "idempotency_keys", "outbox", "transaction_guard", "alembic_version"} <= set(tables)
    with app.state.db.engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM " + ("m3." if schema else "") + "alembic_version")).scalar_one()
    assert version == "0001"


def test_existing_schema_migration_never_requests_database_create(environment):
    _, app, _, _ = environment
    statements = []
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(app.state.db.engine, "before_cursor_execute", record)
    try:
        app.state.db.migrate()
    finally:
        event.remove(app.state.db.engine, "before_cursor_execute", record)
    assert not any("CREATE SCHEMA" in statement.upper() for statement in statements)
    if os.getenv("M3_REQUIRE_SCHEMA_OWNER") == "1":
        assert app.state.db.engine.dialect.name == "postgresql", "Schema-owner acceptance requires PostgreSQL"
        with app.state.db.engine.connect() as connection:
            assert connection.execute(text(
                "SELECT NOT has_database_privilege(current_user, current_database(), 'CREATE')"
            )).scalar_one(), "Use a schema owner without database-level CREATE"
            assert connection.execute(text(
                "SELECT nspowner = (SELECT oid FROM pg_roles WHERE rolname = current_user) "
                "FROM pg_namespace WHERE nspname = 'm3'"
            )).scalar_one(), "Test role must own the provisioned m3 schema"


def test_explicit_development_seeds_are_idempotent_and_not_a_migration(environment):
    _, app, clock, _ = environment
    dev_service = WorkOrderService(app.state.db, app.state.directory,
                                  replace(app.state.settings, mode="development"), clock)
    assert sum(created for _, created in seed(dev_service)) == 2
    assert sum(created for _, created in seed(dev_service)) == 0
    assert len(dev_service.list(app.state.directory.authenticate("demo-admin"))) == 2
    with pytest.raises(ValueError):
        seed(app.state.service)


def test_default_runtime_is_closed_and_does_not_open_development_database(tmp_path):
    db_path = tmp_path / "must-not-exist.sqlite3"
    # Unavailable directory is also fail-closed in development, without opening a stale demo DB.
    app = create_app(Settings(mode="development", database_url=f"sqlite:///{db_path}", worker_enabled=True))
    with TestClient(app) as api:
        assert api.get("/healthz").json() == {"service": "m3-api", "status": "ok"}
        assert api.get(BASE + "/context").json()["businessReady"] is False
        assert api.get(BASE + "/me", headers=auth()).status_code == 503
        assert app.state.worker is None
    assert not db_path.exists()
    production = create_app(Settings())
    with TestClient(production) as api:
        assert api.get(BASE + "/context").json()["demoIdentities"] == []
        assert create(api).status_code == 503
    with pytest.raises(ValueError):
        Settings(mode="production", directory_mode="development")
    with pytest.raises(ValueError):
        Settings(mode="production", database_url=f"sqlite:///{db_path}")


@pytest.mark.parametrize("url,token", [
    ("http://[", "token"), ("http://localhost:invalid", "token"),
    ("http://localhost", "token\r\ninjected"), ("http://localhost", ""),
])
def test_invalid_service_configuration_is_permanent_without_network(url, token):
    with pytest.raises(SyncFailure) as caught:
        M1Client(url, token).apply("source", {"roomId": "room-101", "revision": 1,
            "status": "ACTIVE", "startsAt": "2026-10-27T00:00:00Z"}, "correlation")
    assert caught.value.retryable is False
