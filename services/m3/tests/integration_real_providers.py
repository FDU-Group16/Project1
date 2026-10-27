"""Real M3 -> M1 -> D-02 HTTP/PostgreSQL acceptance; D-01 is synthetic.

Run sequentially through scripts/test-business.py against provisioned disposable
TEST_M1_DATABASE_URL, TEST_D_DATABASE_URL and TEST_M3_DATABASE_URL databases.
No M1/D/M3 business functions or schemas are substituted or directly modified.
The identity fixture can also run alone for local browser verification:
    python services/m3/tests/integration_real_providers.py --identity-fixture --port 3115
This explicit test fixture is not an account system or a deployable D-01 service.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[3]
IDENTITIES = {
    "dev-student-cs": {"displayName": "合成 CS 同学", "departmentId": "cs", "permissions": ["seat:reserve"]},
    "dev-student-ee": {"displayName": "合成 EE 同学", "departmentId": "ee", "permissions": ["seat:reserve"]},
    "dev-room-admin": {"displayName": "合成房间管理员", "departmentId": None, "permissions": ["room:manage"]},
    "dev-operator": {"displayName": "合成运营人员", "departmentId": None, "permissions": ["operations:read"]},
    "dev-repair-admin": {"displayName": "合成物业管理员", "departmentId": None, "permissions": ["repair:dispatch", "repair:report"]},
    "dev-technician-1": {"displayName": "合成维修员一", "departmentId": None, "permissions": ["repair:work", "repair:report"]},
    "dev-technician-2": {"displayName": "合成维修员二", "departmentId": None, "permissions": ["repair:work", "repair:report"]},
}


def identity_fixture(port=0):
    """Create an explicit external identity fixture, reusable by browser tests."""
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Identity-Fixture", "synthetic-test-only")
            self.end_headers()
            self.wfile.write(body)

        def actor(self):
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if token not in IDENTITIES:
                self.reply(401, {"code": "SYNTHETIC_IDENTITY_REJECTED"})
                return None
            return {"id": token, **IDENTITIES[token]}

        def do_GET(self):
            if self.path == "/healthz":
                return self.reply(200, {"status": "ok", "identityMode": "synthetic-test-only"})
            actor = self.actor()
            if actor is None:
                return
            if self.path == "/api/v1/auth/me":
                return self.reply(200, actor)
            if self.path == "/api/v1/repair-technicians":
                if "repair:dispatch" not in actor["permissions"]:
                    return self.reply(403, {"code": "FORBIDDEN"})
                return self.reply(200, {"items": [{"id": key, **value} for key, value in IDENTITIES.items()
                                                  if "repair:work" in value["permissions"]]})
            self.reply(404, {"code": "FIXTURE_PATH_NOT_FOUND"})

        def do_POST(self):
            # Local browser convenience only: username is a published synthetic key.
            # This deliberately makes no authentication or account-security claims.
            if self.path == "/api/v1/auth/logout":
                return self.reply(200, {"status": "test-session-cleared"})
            if self.path != "/api/v1/auth/login":
                return self.reply(404, {"code": "FIXTURE_PATH_NOT_FOUND"})
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 4096)))
                username = body.get("username")
            except (ValueError, AttributeError):
                return self.reply(422, {"code": "INVALID_INPUT"})
            if username not in IDENTITIES:
                return self.reply(401, {"code": "SYNTHETIC_IDENTITY_REJECTED"})
            return self.reply(200, {"accessToken": username, "expiresAt": stamp(datetime.now(timezone.utc) + timedelta(hours=1)),
                                    "user": {"id": username, **IDENTITIES[username]}, "identityMode": "synthetic-test-only"})

        def log_message(self, *args):
            pass  # Never log bearer values or submitted bodies.

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


@contextmanager
def identity_provider():
    server = identity_fixture()
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def sanitized_log_tail(log, environment):
    """Keep startup diagnostics useful without emitting DSNs or credentials."""
    log.flush()
    log.seek(0)
    result = log.read()
    sensitive = [value for key, value in environment.items() if value and any(
        marker in key.upper() for marker in ("DATABASE_URL", "PASSWORD", "TOKEN", "SECRET"))]
    for value in sorted(sensitive, key=len, reverse=True):
        result = result.replace(value, "[REDACTED]")
    result = re.sub(r"postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>]+", "[REDACTED_DATABASE_URL]", result)
    result = re.sub(r"https?://[^/\s\"'<>]+@[^\s\"'<>]+", "[REDACTED_CREDENTIAL_URL]", result)
    return result[-6000:]


def clear_disposable_m3_data():
    """Clear M3 business rows only after an explicit destructive test opt-in."""
    if os.getenv("M3_TEST_ALLOW_RESET") != "1":
        raise RuntimeError("M3_TEST_ALLOW_RESET=1 is required for the exclusively owned disposable test database")
    url = os.environ["TEST_M3_DATABASE_URL"]
    if not url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Explicit TEST_M3_DATABASE_URL must use PostgreSQL")
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1)) as conn:
        present = conn.execute("SELECT to_regclass('m3.work_orders')").fetchone()[0]
        if present:
            # Preserve versioned schema and transaction guard; never touch M1/D.
            conn.execute("TRUNCATE m3.outbox, m3.idempotency_keys, m3.work_orders")


def run():
    for service in ("M1", "D", "M3"):
        if not os.getenv(f"TEST_{service}_DATABASE_URL", "").startswith("postgresql"):
            raise RuntimeError(f"TEST_{service}_DATABASE_URL must explicitly select disposable PostgreSQL")
    clear_disposable_m3_data()
    ports = {service: free_port() for service in ("d", "m1", "m3")}
    env = os.environ.copy()
    env.update({f"{service}_DATABASE_URL": os.environ[f"TEST_{service}_DATABASE_URL"]
                for service in ("M1", "D", "M3")})
    for key in ("D_M1_TOKEN", "M1_M2_TOKEN", "M1_M3_TOKEN", "M1_CHECKIN_SECRET"):
        env[key] = secrets.token_hex(32)
    env.update(APP_ENV="test", M1_USE_DEV_DEPENDENCIES="1", D_USE_DEV_IDENTITY="0",
               D_BASE_URL=f"http://127.0.0.1:{ports['d']}", M3_MODE="production",
               M3_DIRECTORY_MODE="http", M3_M1_MODE="http",
               M3_M1_BASE_URL=f"http://127.0.0.1:{ports['m1']}",
               M3_M1_TOKEN=env["M1_M3_TOKEN"], M3_WORKER_ENABLED="true",
               M3_WORKER_INTERVAL_SECONDS="0.1", M3_M1_TIMEOUT_SECONDS="1")
    processes, logs, reservations_to_cancel = {}, [], []

    def request(service, method, path, token="dev-student-cs", expected=200, **kwargs):
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
        response = httpx.request(method, f"http://127.0.0.1:{ports[service]}{path}",
                                 headers=headers, timeout=10, trust_env=False, **kwargs)
        assert response.status_code == expected, (service, method, path, response.status_code, response.text)
        return response.json()

    def m3_get(order):
        return request("m3", "GET", f"/api/m3/v1/work-orders/{order['id']}", "dev-repair-admin")

    def action(order, name, token, **fields):
        current = m3_get(order)
        return request("m3", "POST", f"/api/m3/v1/work-orders/{order['id']}/{name}", token,
                       json={"version": current["version"], **fields})

    def wait_status(order, status):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            latest = m3_get(order)
            if latest["status"] == status:
                return latest
            if latest["sync"] and latest["sync"]["status"] == "failed":
                raise AssertionError(("M3 sync failed", latest["sync"]))
            time.sleep(0.05)
        raise AssertionError(("Timed out waiting for M3", status, latest["status"], latest["sync"]))

    def create_order(room, title):
        return request("m3", "POST", "/api/m3/v1/work-orders", expected=201,
                       headers={"Idempotency-Key": str(uuid4())}, json={"roomId": room["id"],
                       "category": "electrical", "title": title, "description": "独立真实服务集成验收工单"})

    def start_repair(order):
        action(order, "assign", "dev-repair-admin", assigneeId="dev-technician-1")
        started = action(order, "start", "dev-technician-1")
        assert started["status"] == "BLOCK_PENDING"
        return wait_status(order, "IN_PROGRESS")

    def finish_repair(order):
        completed = action(order, "complete", "dev-technician-1", note="实际维修工作已完成，等待报修人验收")
        assert completed["status"] == "PENDING_ACCEPTANCE"
        return completed

    def accept_repair(order):
        accepted = action(order, "accept", "dev-student-cs")
        assert accepted["status"] == "RELEASE_PENDING"
        return wait_status(order, "CLOSED")

    try:
        with identity_provider() as identity_url:
            env.update(D_IDENTITY_URL=identity_url, M3_IDENTITY_BASE_URL=identity_url)
            for service in ("d", "m1", "m3"):
                log = tempfile.TemporaryFile(mode="w+")
                logs.append(log)
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", f"services.{service}.main:app",
                                            "--host", "127.0.0.1", "--port", str(ports[service])],
                                           cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                processes[service] = process
                for _ in range(200):
                    if process.poll() is not None:
                        diagnostic = sanitized_log_tail(log, env)
                        raise RuntimeError(f"{service} process exited before health readiness (credentials redacted):\n{diagnostic}")
                    try:
                        health = httpx.get(f"http://127.0.0.1:{ports[service]}/healthz", timeout=0.4, trust_env=False)
                        if health.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.05)
                else:
                    raise RuntimeError(f"{service} health readiness timed out")

            context = request("m3", "GET", "/api/m3/v1/context")
            assert context["businessReady"] is True and context["directoryMode"] == "http"
            assert context["mode"] == "production" and context["demoIdentities"] == []
            assert request("m3", "GET", "/api/m3/v1/me")["role"] == "reporter"
            request("m3", "GET", "/api/m3/v1/technicians", "dev-room-admin", expected=403)
            technicians = request("m3", "GET", "/api/m3/v1/technicians", "dev-repair-admin")["items"]
            assert "dev-technician-1" in {person["id"] for person in technicians}

            room_body = {"name": "M3 real HTTP " + uuid4().hex[:8], "departmentId": None,
                         "openHour": 0, "closeHour": 24, "weekdays": list(range(7)), "active": True}
            room = request("d", "POST", "/api/v1/rooms", "dev-room-admin", expected=201, json=room_body)
            seats = [request("d", "POST", f"/api/v1/rooms/{room['id']}/seats", "dev-room-admin", expected=201,
                             json={"number": f"M3-{number:02}", "hasSocket": True, "active": True}) for number in range(1, 4)]
            private = request("d", "POST", "/api/v1/rooms", "dev-room-admin", expected=201,
                              json={**room_body, "name": room_body["name"] + " private", "departmentId": "ee"})
            visible = request("m3", "GET", "/api/m3/v1/rooms")["items"]
            assert room["id"] in {item["id"] for item in visible}
            assert private["id"] not in {item["id"] for item in visible}
            request("m3", "POST", "/api/m3/v1/work-orders", expected=422,
                    headers={"Idempotency-Key": str(uuid4())}, json={"roomId": private["id"], "category": "other",
                    "title": "越权房间必须拒绝", "description": "不可提交其他院系房间"})

            # The existing M1/D integration uses tomorrow at 02:00 UTC; choose a
            # separate slot because M1 correctly blocks overlapping user bookings.
            start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
            interval_a = {"startsAt": stamp(start), "endsAt": stamp(start + timedelta(hours=1))}
            interval_b = {"startsAt": stamp(start + timedelta(hours=1)), "endsAt": stamp(start + timedelta(hours=2))}

            def available(interval):
                # Query as an unbooked student; owner overlap filtering otherwise hides every seat.
                return {seat["id"] for seat in request("m1", "GET", "/api/v1/seats", "dev-student-ee",
                                                        params={**interval, "roomId": room["id"]})["items"]}

            seat_ids = {seat["id"] for seat in seats}
            assert available(interval_a) == seat_ids
            reservation = request("m1", "POST", "/api/v1/reservations", json={**interval_a, "roomId": room["id"],
                                  "seatId": seats[0]["id"]}, headers={"Idempotency-Key": str(uuid4())})
            reservations_to_cancel.append(reservation["id"])
            assert available(interval_a) == seat_ids - {seats[0]["id"]}
            m2_source = "m3-integration-" + uuid4().hex
            m2_payload = {**interval_b, "roomId": room["id"], "revision": 1, "status": "ACTIVE"}
            request("m1", "PUT", "/internal/v1/room-blocks/m2/" + m2_source, env["M1_M2_TOKEN"], json=m2_payload)

            first, second = create_order(room, "灯具损坏"), create_order(room, "插座故障")
            start_repair(first)
            assert available(interval_a) == set(), "M3 must block every seat, including unreserved seats"
            start_repair(second)
            finish_repair(first)
            assert available(interval_a) == set(), "Waiting for acceptance must retain the M3 block"
            accept_repair(first)
            assert available(interval_a) == set(), "A second M3 source must keep the room blocked"
            finish_repair(second)
            assert available(interval_a) == set()
            accept_repair(second)
            assert available(interval_a) == seat_ids - {seats[0]["id"]}, "M3 release must retain an individual reservation"
            assert available(interval_b) == set(), "M3 release must retain the M2 source"
            existing = request("m1", "GET", "/api/v1/reservations/" + reservation["id"])
            assert existing["status"] == "RESERVED" and existing["seatId"] == seats[0]["id"]
            request("m1", "PUT", "/internal/v1/room-blocks/m2/" + m2_source, env["M1_M2_TOKEN"],
                    json={**m2_payload, "revision": 2, "status": "RELEASED"})
            assert available(interval_b) == seat_ids

            provenance = request("m1", "GET", f"/api/v1/rooms/{room['id']}/provenance", "dev-operator", params={"limit": 100})["items"]
            assert {"M1", "M2", "M3"} <= {event["sourceSystem"] for event in provenance}
            m3_events = [event for event in provenance if event["sourceSystem"] == "M3"]
            for order in (first, second):
                source_events = [event for event in m3_events if event["sourceId"] == order["id"]]
                assert {(event["action"], event["detail"]["revision"]) for event in source_events} == {("ACTIVE", 1), ("RELEASED", 2)}
                old = next(event for event in source_events if event["action"] == "ACTIVE")
                request("m1", "PUT", f"/internal/v1/room-blocks/m3/{order['id']}", env["M1_M3_TOKEN"], expected=409,
                        json={"roomId": room["id"], "revision": 1, "status": "ACTIVE", "startsAt": old["detail"]["startsAt"]})
            assert available(interval_a) == seat_ids - {seats[0]["id"]}

            # Credentials, not only application conventions, enforce all three service boundaries.
            for owner in ("m1", "d", "m3"):
                for other, table in (("m1", "reservations"), ("d", "rooms"), ("m3", "work_orders")):
                    if owner == other:
                        continue
                    try:
                        with psycopg.connect(os.environ[f"TEST_{owner.upper()}_DATABASE_URL"]) as conn:
                            conn.execute(sql.SQL("SELECT * FROM {}.{} LIMIT 1").format(sql.Identifier(other), sql.Identifier(table)))
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError(f"{owner} credential can access {other} schema")

            outage = create_order(room, "提供方故障时不得假成功")
            action(outage, "assign", "dev-repair-admin", assigneeId="dev-technician-1")
            processes["d"].terminate()
            processes["d"].wait(timeout=5)
            request("m3", "GET", "/api/m3/v1/rooms", expected=503)
            request("m1", "GET", "/api/v1/seats", "dev-student-ee", expected=503,
                    params={**interval_b, "roomId": room["id"]})
            action(outage, "start", "dev-technician-1")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                pending = m3_get(outage)
                if pending["sync"]["attempts"] >= 1 and pending["sync"]["status"] == "pending":
                    break
                time.sleep(0.05)
            assert pending["status"] == "BLOCK_PENDING" and pending["sync"]["retryable"] is True
            assert pending["sync"]["attempts"] >= 1
            print("PASS real M3 -> M1 -> D-02 HTTP/PostgreSQL: scoped rooms, whole-room repair block, acceptance hold, "
                  "two M3 sources, M2 and reservation preservation, stale-write tombstones, schema credentials and provider outage. "
                  "D-01 uses an explicitly synthetic HTTP fixture; M1 identity/delivery remain explicit development substitutes.")
    finally:
        # Release only reservations created by this scenario via the owning API.
        # No cross-service database cleanup is performed by this consumer test.
        if "m1" in processes and processes["m1"].poll() is None:
            for reservation_id in reservations_to_cancel:
                try:
                    request("m1", "POST", f"/api/v1/reservations/{reservation_id}/cancel")
                except (httpx.HTTPError, AssertionError):
                    print("M3 integration reservation cleanup needs disposable-database reset.", file=sys.stderr)
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()
        clear_disposable_m3_data()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-fixture", action="store_true")
    parser.add_argument("--port", type=int, default=3115)
    options = parser.parse_args()
    if options.identity_fixture:
        server = identity_fixture(options.port)
        print(f"Synthetic D-01 test fixture on http://127.0.0.1:{server.server_port}; never use for production accounts.", flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    else:
        run()
