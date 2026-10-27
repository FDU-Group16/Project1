"""Temporary account behavior on real PostgreSQL; no in-memory auth substitute."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from services.d.main import create_app
from services.d.test_accounts.seed import seed, validate_credentials
from services.d.test_accounts.service import ACCOUNT_SPECS, TestAccountService
from services.platform import Database, Problem, utcnow


class Clock:
    def __init__(self):
        self.now = utcnow()
    def __call__(self):
        return self.now


class TestAccountConfigurationTests(unittest.TestCase):
    def test_default_does_not_register_test_routes(self):
        with patch.dict(os.environ, {"D_TEST_ACCOUNTS_ENABLED": "0", "APP_ENV": "production",
                                     "D_USE_DEV_IDENTITY": "0", "D_DATABASE_URL": ""}):
            with TestClient(create_app()) as client:
                for method, path in (("get", "/api/v1/auth/context"), ("get", "/api/v1/auth/me"),
                                     ("post", "/api/v1/auth/login"), ("post", "/api/v1/auth/logout"),
                                     ("get", "/api/v1/repair-technicians")):
                    self.assertEqual(getattr(client, method)(path).status_code, 404)
                self.assertEqual(client.get("/healthz").json(), {"service": "d-api", "status": "ok"})

    def test_invalid_environment_combinations_fail_before_serving(self):
        for environment in ("production", "development", ""):
            with patch.dict(os.environ, {"D_TEST_ACCOUNTS_ENABLED": "1", "APP_ENV": environment}):
                with self.assertRaises(RuntimeError):
                    create_app()
        with patch.dict(os.environ, {"D_TEST_ACCOUNTS_ENABLED": "yes", "APP_ENV": "test"}):
            with self.assertRaises(RuntimeError):
                create_app()

    def test_credentials_preflight_and_lifetime_never_echo_secrets(self):
        good = {name: secrets.token_urlsafe(24) for name, _, _ in ACCOUNT_SPECS}
        self.assertTrue(validate_credentials(good) == good, "Credential preflight changed the supplied values")
        for invalid in ({}, {**good, "other": secrets.token_urlsafe(24)},
                        {**good, "m3-student": "short"}, {**good, "m3-student": "x" * 129},
                        {**good, "m3-student": " " * 24}, {**good, "m3-admin": good["m3-student"]}):
            with self.assertRaises(ValueError) as caught:
                validate_credentials(invalid)
            self.assertNotIn(good["m3-student"], str(caught.exception))
        with patch.dict(os.environ, {"D_TEST_ACCOUNTS_ENABLED": "1", "APP_ENV": "test"}):
            for days in (0, 31, True):
                with self.assertRaises(ValueError):
                    seed("/private/nonexistent/test-accounts.json", days)


@unittest.skipUnless(os.getenv("TEST_D_DATABASE_URL"), "Requires disposable PostgreSQL TEST_D_DATABASE_URL")
class TestAccountPostgresTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["TEST_D_DATABASE_URL"]
        if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
            self.fail("Refusing to clear test account tables outside an explicitly named test database")
        self.environment = patch.dict(os.environ, {"D_DATABASE_URL": url, "D_TEST_ACCOUNTS_ENABLED": "1",
                                                  "APP_ENV": "test", "D_USE_DEV_IDENTITY": "0"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.db, self.clock = Database("d"), Clock()
        self.db.migrate(Path(__file__).parents[1] / "migrations")
        self.clear()
        self.addCleanup(self.clear)
        self.temporary = tempfile.TemporaryDirectory(prefix="d-test-accounts-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "credentials.txt"
        self.credentials = {name: secrets.token_urlsafe(24) for name, _, _ in ACCOUNT_SPECS}
        seed(self.output, credentials=self.credentials, database=self.db, clock=self.clock)
        self.app = create_app()
        self.app.state.test_accounts.clock = self.clock
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def clear(self):
        with self.db.connection() as conn:
            conn.execute("TRUNCATE test_sessions, test_accounts, test_login_limits")

    def login(self, username="m3-student", password=None, **headers):
        return self.client.post("/api/v1/auth/login", json={"username": username,
            "password": password if password is not None else self.credentials.get(username, "not-a-valid-password")}, headers=headers)

    @staticmethod
    def bearer(session):
        return {"Authorization": "Bearer " + session["accessToken"]}

    def test_password_login_private_storage_refresh_and_logout(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.text)
        session = response.json()
        self.assertTrue(session["user"]["testAccount"])
        self.assertEqual(set(session["user"]["permissions"]), {"repair:report", "seat:reserve"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-identity-mode"], "test-accounts")
        self.assertNotIn(self.credentials["m3-student"], response.text)
        with self.db.connection() as conn:
            rows = conn.execute("SELECT * FROM test_accounts ORDER BY username").fetchall()
            self.assertEqual(len({bytes(row["password_salt"]) for row in rows}), 4)
            self.assertTrue(all(row["password_iterations"] == 600000 for row in rows))
            stored = conn.execute("SELECT token_digest FROM test_sessions").fetchone()["token_digest"]
            self.assertEqual(bytes(stored), hashlib.sha256(session["accessToken"].encode()).digest())
            self.assertNotIn(session["accessToken"], repr(rows))
            self.assertTrue(all(secret not in repr(rows) for secret in self.credentials.values()))
        # A fresh application/service uses persisted session state, not memory.
        fresh = TestAccountService(Database("d"), self.clock)
        self.assertEqual(fresh.current(self.bearer(session)["Authorization"]), session["user"])
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.bearer(session)).json(), session["user"])
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=self.bearer(session)).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.bearer(session)).status_code, 401)
        with self.assertRaises(Problem):
            fresh.current(self.bearer(session)["Authorization"])

    def test_unknown_bad_expired_and_disabled_accounts_are_same_failure(self):
        bad = self.login(password="wrong-password").json()
        unknown = self.login("unknown-account").json()
        self.assertEqual(bad, unknown)
        with self.db.connection() as conn:
            conn.execute("UPDATE test_accounts SET disabled=true WHERE username='m3-student'")
        disabled = self.login()
        self.assertEqual(disabled.status_code, 401)
        self.assertEqual(disabled.json(), bad)
        self.clock.now += timedelta(days=7)
        expired = self.login("m3-admin")
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(expired.json(), bad)
        self.assertEqual(expired.headers["cache-control"], "no-store")
        for forged in ("dev-student-cs", "m3-student", "A" * 43):
            self.assertEqual(self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + forged}).status_code, 401)

    def test_session_and_account_expiry_and_roster_authorization(self):
        admin, student = self.login("m3-admin").json(), self.login().json()
        self.assertEqual(self.client.get("/api/v1/repair-technicians", headers=self.bearer(student)).status_code, 403)
        roster = self.client.get("/api/v1/repair-technicians", headers=self.bearer(admin)).json()["items"]
        self.assertEqual({item["id"] for item in roster}, {"test-m3-worker1", "test-m3-worker2"})
        self.assertTrue(all("room:manage" not in item["permissions"] and "operations:read" not in item["permissions"] for item in roster))
        with self.db.connection() as conn:
            conn.execute("UPDATE test_accounts SET expires_at=%s WHERE username='m3-worker1'", (self.clock.now + timedelta(minutes=30),))
            conn.execute("UPDATE test_accounts SET disabled=true WHERE username='m3-worker2'")
        worker = self.login("m3-worker1").json()
        self.assertEqual(worker["expiresAt"], (self.clock.now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"))
        self.clock.now += timedelta(minutes=30)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.bearer(worker)).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/repair-technicians", headers=self.bearer(admin)).json(), {"items": []})
        self.clock.now += timedelta(minutes=90)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=self.bearer(admin)).status_code, 401)

    def test_known_unknown_limits_persist_and_ignore_spoofed_proxy_identity(self):
        for username in ("m3-student", "unknown"):
            for index in range(5):
                self.assertEqual(self.login(username, "wrong", **{"X-Forwarded-For": f"192.0.2.{index}"}).status_code, 401)
            result = self.login(username, "wrong", **{"X-Forwarded-For": "198.51.100.9"})
            self.assertEqual(result.status_code, 429)
            self.assertEqual(result.headers["cache-control"], "no-store")
        with self.assertRaises(Problem) as caught:
            TestAccountService(Database("d"), self.clock).login("m3-student", self.credentials["m3-student"])
        self.assertEqual(caught.exception.status, 429)
        self.clock.now += timedelta(minutes=15)
        self.assertEqual(self.login().status_code, 200)

    def test_global_limit_and_concurrent_admission_are_durable(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(lambda _: self.login("m3-student", "wrong").status_code, range(10)))
        self.assertEqual(sorted(statuses), [401] * 5 + [429] * 5)
        with self.db.connection() as conn:
            conn.execute("UPDATE test_login_limits SET attempts=100 WHERE bucket='all'")
        self.assertEqual(self.login("new-unknown-name").status_code, 429)
        self.assertEqual(self.login("m3-admin").status_code, 429)

    def test_seed_idempotence_file_permissions_and_no_password_rotation(self):
        original, original_stat = self.output.read_bytes(), self.output.stat()
        with self.db.connection() as conn:
            before = conn.execute("SELECT * FROM test_accounts ORDER BY username").fetchall()
        result = seed(self.output, days=30, database=self.db, clock=self.clock)
        self.assertEqual(result, {"created": 0, "existing": 4})
        self.assertTrue(self.output.read_bytes() == original, "Private output changed during idempotent seed")
        self.assertEqual(self.output.stat().st_mtime_ns, original_stat.st_mtime_ns)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT * FROM test_accounts ORDER BY username").fetchall(), before)
        wrong = {**self.credentials, "m3-student": secrets.token_urlsafe(24)}
        with self.assertRaises(ValueError):
            seed(self.output, credentials=wrong, database=self.db, clock=self.clock)
        missing = Path(self.temporary.name) / "redelivered.txt"
        with self.assertRaises(ValueError):
            seed(missing, database=self.db, clock=self.clock)
        self.assertFalse(missing.exists())
        seed(missing, credentials=self.credentials, database=self.db, clock=self.clock)
        self.assertTrue(json.loads(missing.read_text()) == json.loads(original), "Private redelivery differs")
        self.output.chmod(0o644)
        with self.assertRaises(ValueError):
            seed(self.output, credentials=self.credentials, database=self.db, clock=self.clock)

    def test_seed_stdin_cli_preserves_output_and_never_logs_credentials(self):
        command = [sys.executable, "-m", "services.d.test_accounts.seed", "--output", str(self.output), "--credentials-stdin"]
        before = self.output.read_bytes()
        result = subprocess.run(command, input=json.dumps(self.credentials), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.output.read_bytes() == before, "Private CLI output changed")
        self.assertTrue(all(secret not in result.stdout + result.stderr for secret in self.credentials.values()))
        wrong = {**self.credentials, "m3-admin": secrets.token_urlsafe(24)}
        rejected = subprocess.run(command, input=json.dumps(wrong), text=True, capture_output=True, timeout=30)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertTrue(all(secret not in rejected.stdout + rejected.stderr for secret in wrong.values()))
        self.assertTrue(self.output.read_bytes() == before, "Rejected input modified private output")

    def test_seed_recovers_private_delivery_after_database_transaction_rollback(self):
        self.clear()
        output = Path(self.temporary.name) / "interrupted.txt"
        database = self.db
        class FailCommit:
            def migrate(self, directory):
                database.migrate(directory)
            @contextmanager
            def connection(self):
                with database.connection() as connection:
                    yield connection
                    raise RuntimeError("Simulate loss before transaction commit")
        with self.assertRaises(RuntimeError):
            seed(output, database=FailCommit(), clock=self.clock)
        saved = output.read_bytes()
        with self.db.connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) AS count FROM test_accounts").fetchone()["count"], 0)
        self.clock.now += timedelta(seconds=10)
        self.assertEqual(seed(output, database=self.db, clock=self.clock), {"created": 4, "existing": 0})
        self.assertTrue(output.read_bytes() == saved, "Recovery changed the private output")
        for account in json.loads(saved)["accounts"]:
            result = TestAccountService(self.db, self.clock).login(account["username"], account["password"])
            self.assertEqual(result["user"], account["user"])

    def test_context_and_strict_input_never_expose_private_data(self):
        context = self.client.get("/api/v1/auth/context")
        self.assertEqual(context.json(), {"mode": "test-accounts"})
        self.assertEqual(context.headers["cache-control"], "no-store")
        password = self.credentials["m3-student"]
        for payload in ({"username": "m3-student", "password": password, "role": "admin"},
                        {"username": False, "password": password}, {"username": "m3-student", "password": ""}):
            response = self.client.post("/api/v1/auth/login", json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(password, response.text)
            self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
