"""Explicit CLI-only real password-account -> D/M1/M3 integration acceptance.

This file deliberately has no pytest test functions and never starts processes
on import. Run it separately against exclusively owned TEST_* PostgreSQL URLs
with M3_TEST_ALLOW_RESET=1. No development identity fixture or authentication mock
is used. Temporary identity tables are cleared, but D-02/M1 business rows remain.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg.conninfo import conninfo_to_dict

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.m3.tests.integration_real_providers import (
    ROOT, clear_disposable_m3_data, free_port, sanitized_log_tail, stamp,
)


EXPECTED_PERMISSIONS = {
    "m3-student": {"repair:report", "seat:reserve"},
    "m3-admin": {"repair:dispatch", "repair:report"},
    "m3-worker1": {"repair:work", "repair:report"},
    "m3-worker2": {"repair:work", "repair:report"},
}


def clear_test_identity_tables():
    if os.getenv("M3_TEST_ALLOW_RESET") != "1":
        raise RuntimeError("Explicit M3_TEST_ALLOW_RESET=1 is required for the exclusively owned test database")
    url = os.environ["TEST_D_DATABASE_URL"]
    if not url.startswith("postgresql://"):
        raise RuntimeError("Explicit TEST_D_DATABASE_URL must use PostgreSQL")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        raise RuntimeError("Refusing to clear identity tables outside an explicitly named test database")
    with psycopg.connect(url) as conn:
        if conn.execute("SELECT to_regclass('d.test_accounts')").fetchone()[0]:
            conn.execute("TRUNCATE d.test_sessions, d.test_accounts, d.test_login_limits")


def run():
    for service in ("M1", "D", "M3"):
        if not os.getenv(f"TEST_{service}_DATABASE_URL", "").startswith("postgresql://"):
            raise RuntimeError(f"Explicit disposable TEST_{service}_DATABASE_URL is required")
        if "test" not in conninfo_to_dict(os.environ[f"TEST_{service}_DATABASE_URL"]).get("dbname", "").lower():
            raise RuntimeError(f"TEST_{service}_DATABASE_URL must identify an explicitly named test database")
    if os.getenv("M3_TEST_ALLOW_RESET") != "1":
        raise RuntimeError("M3_TEST_ALLOW_RESET=1 is required; never run against a shared database")
    clear_disposable_m3_data()
    clear_test_identity_tables()
    ports = {service: free_port() for service in ("d", "m1", "m3")}
    env = os.environ.copy()
    env.update({f"{service}_DATABASE_URL": os.environ[f"TEST_{service}_DATABASE_URL"]
                for service in ("M1", "D", "M3")})
    for key in ("D_M1_TOKEN", "M1_M2_TOKEN", "M1_M3_TOKEN", "M1_CHECKIN_SECRET"):
        env[key] = secrets.token_hex(32)
    env.update(APP_ENV="test", D_TEST_ACCOUNTS_ENABLED="1", D_USE_DEV_IDENTITY="0", M1_USE_DEV_DEPENDENCIES="0",
               D_BASE_URL=f"http://127.0.0.1:{ports['d']}", D_IDENTITY_URL=f"http://127.0.0.1:{ports['d']}",
               M3_MODE="production", M3_DIRECTORY_MODE="http", M3_M1_MODE="http",
               M3_IDENTITY_BASE_URL=f"http://127.0.0.1:{ports['d']}",
               M3_M1_BASE_URL=f"http://127.0.0.1:{ports['m1']}", M3_M1_TOKEN=env["M1_M3_TOKEN"],
               M3_WORKER_ENABLED="true", M3_WORKER_INTERVAL_SECONDS="0.1", M3_M1_TIMEOUT_SECONDS="2")
    processes, logs, sessions = {}, [], {}

    def command(arguments, *, input_text=None, expect_success=True):
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env, input=input_text,
                                capture_output=True, text=True, timeout=60)
        if bool(result.returncode == 0) != expect_success:
            # No credential file or seed output is printed, even on failure.
            raise RuntimeError(f"Test preparation command failed: {arguments[0] if arguments else 'python'}")

    def start(service):
        log = tempfile.TemporaryFile(mode="w+")
        logs.append(log)
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", f"services.{service}.main:app", "--host",
                                    "127.0.0.1", "--port", str(ports[service])], cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT)
        processes[service] = process
        for _ in range(200):
            if process.poll() is not None:
                raise RuntimeError(f"{service} startup failed (redacted):\n{sanitized_log_tail(log, env)}")
            try:
                if httpx.get(f"http://127.0.0.1:{ports[service]}/healthz", timeout=0.4, trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"{service} startup timed out")

    def request(service, method, path, account=None, expected=200, token=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if token is not None or account is not None:
            bearer = token if token is not None else sessions[account]["accessToken"]
            headers["Authorization"] = "Bearer " + bearer
        response = httpx.request(method, f"http://127.0.0.1:{ports[service]}{path}", headers=headers,
                                 timeout=10, trust_env=False, **kwargs)
        if response.status_code != expected:
            # Login responses may contain a session: do not include bodies here.
            raise AssertionError(f"{service} {method} {path}: expected {expected}, received {response.status_code}")
        if "/auth/" in path:
            assert "no-store" in response.headers.get("Cache-Control", ""), "Authentication responses must not be cached"
        return response.json() if response.status_code != 204 else None

    def get_order(order):
        return request("m3", "GET", f"/api/m3/v1/work-orders/{order['id']}", "m3-admin")

    def action(order, name, account, expected=200, **payload):
        current = get_order(order)
        return request("m3", "POST", f"/api/m3/v1/work-orders/{order['id']}/{name}", account, expected=expected,
                       json={"version": current["version"], **payload})

    def wait_status(order, target):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            current = get_order(order)
            if current["status"] == target:
                return current
            if current["sync"] and current["sync"]["status"] == "failed":
                raise AssertionError("Real M3 writeback stopped before the expected state")
            time.sleep(0.05)
        raise AssertionError(f"M3 did not reach {target}")

    try:
        with tempfile.TemporaryDirectory(prefix="m3-test-account-credentials-") as temporary:
            output = Path(temporary) / "accounts.json"
            # Existing D-02 seed creates only stable synthetic master data and
            # never grants a room-management permission to a test account.
            command(["-m", "services.d.seed"])
            supplied_passwords = {username: secrets.token_urlsafe(24) for username in EXPECTED_PERMISSIONS}
            for username, password in supplied_passwords.items():
                env[f"REDACT_{username}_PASSWORD"] = password
            seed_args = ["-m", "services.d.test_accounts.seed", "--output", str(output), "--days", "7",
                         "--credentials-stdin"]
            command(seed_args, input_text=json.dumps(supplied_passwords))
            assert stat.S_IMODE(output.stat().st_mode) == 0o600
            first_seed = output.read_bytes()
            data = json.loads(first_seed)
            credentials = {item["username"]: item for item in data["accounts"]}
            assert set(credentials) == set(EXPECTED_PERMISSIONS)
            assert len({item["password"] for item in credentials.values()}) == 4
            for username, item in credentials.items():
                env[f"REDACT_{username}_PASSWORD"] = item["password"]
            assert all(credentials[username]["password"] == password for username, password in supplied_passwords.items())
            command(seed_args, input_text=json.dumps(supplied_passwords))
            assert output.read_bytes() == first_seed, "Repeated seed must not rotate passwords, expiry or the private output"
            command(seed_args, input_text=json.dumps({username: secrets.token_urlsafe(24)
                                                     for username in EXPECTED_PERMISSIONS}), expect_success=False)
            assert output.read_bytes() == first_seed, "Conflicting supplied credentials must not replace the private output"

            for service in ("d", "m1", "m3"):
                start(service)
            context = request("d", "GET", "/api/v1/auth/context")
            assert context == {"mode": "test-accounts"}
            request("d", "POST", "/api/v1/auth/login", expected=401, json={"username": "m3-student", "password": "incorrect"})
            request("d", "POST", "/api/v1/auth/login", expected=401, json={"username": "unknown-account", "password": "incorrect"})
            for username, item in credentials.items():
                session = request("d", "POST", "/api/v1/auth/login", json={"username": username, "password": item["password"]})
                sessions[username] = session
                env[f"REDACT_{username}_TOKEN"] = session["accessToken"]
                assert len(session["accessToken"]) >= 43 and session["accessToken"] not in credentials
                assert set(session["user"]["permissions"]) == EXPECTED_PERMISSIONS[username]
                assert session["user"]["testAccount"] is True
                assert session["user"]["departmentId"] is None
                expires = datetime.fromisoformat(session["expiresAt"].replace("Z", "+00:00"))
                assert datetime.now(timezone.utc) < expires <= datetime.now(timezone.utc) + timedelta(hours=2, seconds=2)
                assert request("d", "GET", "/api/v1/auth/me", username) == session["user"]
            assert len({item["accessToken"] for item in sessions.values()}) == 4

            # Plaintext passwords and bearer values must not be persisted in D.
            with psycopg.connect(os.environ["TEST_D_DATABASE_URL"]) as conn:
                accounts_data = json.dumps(conn.execute("SELECT row_to_json(t) FROM d.test_accounts t").fetchall(), default=str)
                sessions_data = json.dumps(conn.execute("SELECT row_to_json(t) FROM d.test_sessions t").fetchall(), default=str)
                assert all(item["password"] not in accounts_data for item in credentials.values())
                assert all(item["accessToken"] not in sessions_data for item in sessions.values())

            # Restart the real provider. Existing server-side sessions must remain
            # usable for refresh; no caller-side synthetic session branch is used.
            processes["d"].terminate()
            processes["d"].wait(timeout=5)
            start("d")
            assert request("d", "GET", "/api/v1/auth/me", "m3-student") == sessions["m3-student"]["user"]
            assert request("m3", "GET", "/api/m3/v1/me", "m3-student")["role"] == "reporter"
            rooms = request("m3", "GET", "/api/m3/v1/rooms", "m3-student")["items"]
            assert "demo-room-public" in {room["id"] for room in rooms}
            assert not {"demo-room-cs", "demo-room-ee"} & {room["id"] for room in rooms}
            request("d", "GET", "/api/v1/repair-technicians", "m3-student", expected=403)
            request("m3", "GET", "/api/m3/v1/technicians", "m3-worker1", expected=403)
            roster = request("m3", "GET", "/api/m3/v1/technicians", "m3-admin")["items"]
            assert {item["id"] for item in roster} == {sessions[name]["user"]["id"] for name in ("m3-worker1", "m3-worker2")}
            request("d", "POST", "/api/v1/rooms", "m3-admin", expected=403,
                    json={"name": "Must not be created", "openHour": 8, "closeHour": 22, "weekdays": [0]})
            order = request("m3", "POST", "/api/m3/v1/work-orders", "m3-student", expected=201,
                            headers={"Idempotency-Key": str(uuid4())}, json={"roomId": "demo-room-public", "category": "electrical",
                            "title": "真实密码账号集成验收", "description": "通过真实登录、D02、M3与M1验证完整流程"})
            request("m3", "GET", f"/api/m3/v1/work-orders/{order['id']}", "m3-worker2", expected=404)
            action(order, "assign", "m3-student", expected=403, assigneeId=sessions["m3-worker1"]["user"]["id"])
            action(order, "assign", "m3-admin", assigneeId=sessions["m3-worker1"]["user"]["id"])
            action(order, "start", "m3-worker2", expected=404)
            start_at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=6, minute=0, second=0, microsecond=0)
            query = {"roomId": "demo-room-public", "startsAt": stamp(start_at), "endsAt": stamp(start_at + timedelta(hours=1))}
            seats = request("m1", "GET", "/api/v1/seats", "m3-student", params=query)["items"]
            assert seats, "Real M1 must accept the newly authenticated student and find seeded seats"
            action(order, "start", "m3-worker1")
            wait_status(order, "IN_PROGRESS")
            assert request("m1", "GET", "/api/v1/seats", "m3-student", params=query)["items"] == []
            action(order, "complete", "m3-worker1", note="灯具及线路修复完成")
            assert request("m1", "GET", "/api/v1/seats", "m3-student", params=query)["items"] == []
            action(order, "accept", "m3-worker1", expected=403, note="维修人员不能自验")
            action(order, "accept", "m3-student")
            wait_status(order, "CLOSED")
            assert request("m1", "GET", "/api/v1/seats", "m3-student", params=query)["items"] == seats
            rated = action(order, "rate", "m3-student", score=5, comment="全流程通过真实密码账号完成")
            assert rated["rating"]["score"] == 5

            old_token = sessions["m3-student"]["accessToken"]
            request("d", "POST", "/api/v1/auth/logout", "m3-student", expected=204)
            request("d", "GET", "/api/v1/auth/me", token=old_token, expected=401)
            request("m3", "GET", "/api/m3/v1/me", token=old_token, expected=401)
            request("m1", "GET", "/api/v1/seats", token=old_token, expected=401, params=query)
            assert request("d", "GET", "/api/v1/auth/me", "m3-admin")["id"] == sessions["m3-admin"]["user"]["id"]
            for attempt in range(5):
                request("d", "POST", "/api/v1/auth/login", expected=401,
                        headers={"X-Forwarded-For": f"192.0.2.{attempt + 1}"},
                        json={"username": "limited-unknown", "password": "incorrect"})
            processes["d"].terminate()
            processes["d"].wait(timeout=5)
            start("d")
            request("d", "POST", "/api/v1/auth/login", expected=429,
                    headers={"X-Forwarded-For": "198.51.100.1"},
                    json={"username": "limited-unknown", "password": "incorrect"})
            print("PASS real temporary password accounts -> D/M1/M3: four least-privilege identities, private idempotent seed, "
                  "hashed storage, wrong-password rejection, restart/refresh, cross-role denial, repair lifecycle, logout revocation "
                  "and persistent username throttling despite forged proxy headers. "
                  "Temporary test accounts are not the formal campus D-01 provider.")
    finally:
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
        clear_test_identity_tables()


if __name__ == "__main__":
    run()
