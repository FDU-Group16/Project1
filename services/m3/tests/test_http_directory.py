"""HTTP consumer boundary tests; real-provider integration has its own script."""
from dataclasses import replace
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from services.m3.database import orders
from services.m3.http_directory import DirectoryFailure, HttpDirectory, identity_record
from services.m3.main import create_app
from services.m3.ports import Actor
from services.m3.settings import Settings
from services.m3.tests.test_api import BASE, PAYLOAD, action, auth, create, environment


def identity(identifier, permissions, department="cs"):
    return {"id": identifier, "displayName": identifier, "departmentId": department, "permissions": permissions}


@pytest.fixture
def http_environment(environment):
    _, original, clock, deliveries = environment
    state = {
        "identities": {
            "student": identity("student", ["seat:reserve"]),
            "room-admin": identity("room-admin", ["room:manage"]),
            "operator": identity("operator", ["operations:read"]),
            "admin": identity("admin", ["repair:dispatch", "repair:report"], None),
            "mixed": identity("mixed", ["repair:dispatch", "repair:work", "repair:report"], None),
            "worker": identity("worker", ["repair:work"], None),
        },
        "rooms": {"items": [
            {"id": "room-101", "name": "公共自习室", "active": True, "retired": False},
            {"id": "closed", "name": "已关闭", "active": False, "retired": False},
            {"id": "retired", "name": "已撤销", "active": True, "retired": True},
        ]},
        "roster": {"items": [identity("mixed", ["repair:dispatch", "repair:work"], None),
                                identity("worker", ["repair:work"], None)]},
        "calls": [], "status": {}, "on_roster": None,
    }

    def receive(request):
        token = request.headers["authorization"][7:]
        state["calls"].append((request.url.host, request.url.path, token))
        if request.url.path in state["status"]:
            return httpx.Response(state["status"][request.url.path], json={"secret": "do-not-forward"})
        if request.url.path == "/api/v1/auth/me":
            return (httpx.Response(200, json=state["identities"][token]) if token in state["identities"]
                    else httpx.Response(401))
        if request.url.path == "/api/v1/rooms":
            return httpx.Response(200, json=state["rooms"])
        if request.url.path == "/api/v1/repair-technicians":
            if state["on_roster"]:
                state["on_roster"]()
            return httpx.Response(200, json=state["roster"])
        return httpx.Response(404)

    settings = replace(original.state.settings, directory_mode="http", m1_mode="http",
                       identity_base_url="http://identity.invalid", d_base_url="http://rooms.invalid")
    directory = HttpDirectory(settings.identity_base_url, settings.d_base_url,
                              transport=httpx.MockTransport(receive))
    app = create_app(settings, directory=directory, db=original.state.db, clock=clock,
                     m1_client=original.state.worker.client)
    with TestClient(app) as api:
        yield api, app, state, clock, deliveries


def test_http_identity_is_revalidated_and_never_grants_room_admin_repair_authority(http_environment):
    api, _, state, _, _ = http_environment
    assert api.get(BASE + "/me", headers=auth("student")).json() == {"id": "student", "name": "student", "role": "reporter"}
    for token in ("room-admin", "operator"):
        assert api.get(BASE + "/me", headers=auth(token)).status_code == 403
    state["identities"].pop("student")
    assert api.get(BASE + "/me", headers=auth("student")).status_code == 401
    assert api.get(BASE + "/context").json()["demoIdentities"] == []


def test_rooms_use_current_user_token_and_visible_active_directory(http_environment):
    api, app, state, _, _ = http_environment
    assert api.get(BASE + "/rooms", headers=auth("student")).json() == {"items": [{"id": "room-101", "name": "公共自习室"}]}
    assert ("rooms.invalid", "/api/v1/rooms", "student") in state["calls"]
    for hidden in ("closed", "retired", "other-department"):
        assert create(api, token="student", key=hidden, payload={**PAYLOAD, "roomId": hidden}).status_code == 422
    order = create(api, token="student").json()
    assert order["reporterId"] == "student"
    with app.state.db.transaction() as connection:
        raw = connection.execute(select(orders.c.data).where(orders.c.id == order["id"])).scalar_one()
    assert raw["_dependencyModes"] == {"directory": "http", "m1": "http"}
    assert "bearer" not in json.dumps(raw) and "permissions" not in json.dumps(raw)


def test_http_multirole_works_and_cannot_self_accept(http_environment):
    api, app, _, _, _ = http_environment
    assert api.get(BASE + "/me", headers=auth("mixed")).json()["role"] == "admin"
    order = create(api, token="student").json()
    order = action(api, order, "assign", "admin", assigneeId="mixed").json()
    order = action(api, order, "start", "mixed").json()
    assert order["status"] == "BLOCK_PENDING"
    app.state.worker.run_once()
    order = api.get(BASE + "/work-orders/" + order["id"], headers=auth("mixed")).json()
    order = action(api, order, "complete", "mixed", note="已维修").json()
    assert order["status"] == "PENDING_ACCEPTANCE"
    assert action(api, order, "accept", "mixed", note="管理员身份也不可自验").status_code == 403
    assert action(api, order, "accept", "student").status_code == 200


def test_report_permission_is_required_even_for_a_valid_repair_identity(http_environment):
    api, _, _, _, _ = http_environment
    assert api.get(BASE + "/me", headers=auth("worker")).status_code == 200
    assert create(api, token="worker").status_code == 403
    assert api.get(BASE + "/technicians", headers=auth("student")).status_code == 403


def test_removing_work_permission_revokes_an_assignees_access_on_next_request(http_environment):
    api, _, state, _, _ = http_environment
    order = create(api, token="student").json()
    order = action(api, order, "assign", "admin", assigneeId="worker").json()
    assert api.get(BASE + "/work-orders/" + order["id"], headers=auth("worker")).status_code == 200
    state["identities"]["worker"]["permissions"] = ["repair:report"]
    assert api.get(BASE + "/work-orders/" + order["id"], headers=auth("worker")).status_code == 404
    assert api.get(BASE + "/work-orders", headers=auth("worker")).json()["items"] == []
    assert action(api, order, "start", "worker").status_code == 404


def test_roster_io_runs_outside_transaction_and_rechecks_version(http_environment):
    api, app, state, _, _ = http_environment
    order = create(api, token="student").json()
    # A provider callback changes the order while the external roster is fetched.
    # SQLite BEGIN IMMEDIATE would fail if the network call held the first tx.
    state["on_roster"] = lambda: app.state.service.act(
        order["id"], "cancel", Actor("student", "student", "reporter"),
        {"version": order["version"], "note": "目录响应前撤回"})
    result = action(api, order, "assign", "admin", assigneeId="worker")
    assert result.status_code == 409 and result.json()["error"]["code"] == "VERSION_CONFLICT"
    latest = api.get(BASE + "/work-orders/" + order["id"], headers=auth("student")).json()
    assert latest["status"] == "CANCELLED" and latest["assigneeId"] is None


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 403), (404, 503), (302, 503), (500, 503), (503, 503)])
def test_directory_errors_are_sanitized_and_do_not_fallback(http_environment, status, expected):
    api, _, state, _, _ = http_environment
    state["status"]["/api/v1/rooms"] = status
    result = api.get(BASE + "/rooms", headers=auth("student"))
    assert result.status_code == expected
    assert "do-not-forward" not in result.text and "room-101" not in result.text


@pytest.mark.parametrize("broken", [
    {"id": "forged", "displayName": "fake", "departmentId": None, "permissions": "repair:dispatch"},
    {"id": "forged", "displayName": "fake", "departmentId": None, "permissions": [False]},
    {"id": "forged", "displayName": "fake", "permissions": ["repair:dispatch"]},
])
def test_malformed_identity_fails_closed(http_environment, broken):
    api, _, state, _, _ = http_environment
    state["identities"]["student"] = broken
    assert api.get(BASE + "/me", headers=auth("student")).status_code == 503


def test_bad_roster_cannot_assign_and_unavailable_rooms_do_not_hide_existing_order(http_environment):
    api, _, state, _, _ = http_environment
    order = create(api, token="student").json()
    state["roster"] = {"items": [{"id": "worker", "displayName": "worker", "permissions": ["repair:work"]}]}
    assert api.get(BASE + "/technicians", headers=auth("admin")).json()["items"] == [
        {"id": "worker", "name": "worker", "role": "technician"}]
    state["roster"] = {"items": [identity("worker", ["room:manage"])]}
    assert action(api, order, "assign", "admin", assigneeId="worker").status_code == 503
    state["status"]["/api/v1/rooms"] = 503
    assert api.get(BASE + "/work-orders/" + order["id"], headers=auth("student")).status_code == 200
    assert create(api, token="student", key="another").status_code == 503


def test_production_without_complete_http_configuration_never_opens_database(tmp_path):
    settings = Settings(directory_mode="http", identity_base_url="http://identity.invalid",
                        d_base_url="http://rooms.invalid", database_url="postgresql+psycopg://invalid/unreachable")
    app = create_app(settings)
    with TestClient(app) as api:
        assert api.get(BASE + "/context").json()["businessReady"] is False
        assert api.get(BASE + "/me", headers=auth("student")).status_code == 503
        assert app.state.db is None and app.state.worker is None


def test_development_records_cannot_be_reclassified_for_production(environment, http_environment):
    original_api, original, _, _ = environment
    create(original_api)
    _, app, _, _, _ = http_environment
    with pytest.raises(ValueError, match="separate database"):
        app.state.service.assert_production_data()
    assert original.state.service.list(Actor("admin-1", "admin", "admin"))


def test_http_transport_failure_and_redirect_never_forward_user_secret():
    seen = []
    def receive(request):
        seen.append(str(request.url))
        return httpx.Response(307, headers={"Location": "http://other.invalid/stolen"})
    directory = HttpDirectory("http://identity.invalid", "http://rooms.invalid",
                              transport=httpx.MockTransport(receive))
    with pytest.raises(DirectoryFailure) as failure:
        directory.authenticate("synthetic-private-token")
    assert failure.value.status == 503 and len(seen) == 1
    assert "synthetic-private-token" not in str(failure.value)
    assert "synthetic-private-token" not in repr(identity_record(identity("student", ["seat:reserve"]), "synthetic-private-token"))
    def timeout(request):
        raise httpx.ReadTimeout("do not expose remote detail")
    directory.transport = httpx.MockTransport(timeout)
    with pytest.raises(DirectoryFailure) as failure:
        directory.authenticate("synthetic-private-token")
    assert failure.value.status == 503 and "remote detail" not in str(failure.value)
