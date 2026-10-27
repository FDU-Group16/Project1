#!/usr/bin/env python3
"""Run real setup scripts against isolated SSH/Docker/DB boundaries, never a server.

All credentials here are synthetic test strings. The subprocess tests execute
the production shell scripts; only external commands are replaced, so stdin,
argument handling, default opt-out and log redaction remain under test.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("staging_account_bootstrap", ROOT / "scripts/bootstrap-test-accounts.py")
BOOTSTRAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOTSTRAP)
PASSWORDS = {name: f"fixture-only-password-{index}-not-real" for index, name in enumerate(
    ("m3-student", "m3-admin", "m3-worker1", "m3-worker2"))}
MAPPING = json.dumps(PASSWORDS)
SHA = "a" * 40


FAKE_PROGRAM = r'''import json
import os
from pathlib import Path
import sys

program, args = Path(sys.argv[0]).name, sys.argv[1:]
if program == "readlink":
    print(str(Path(args[-1]).resolve()))
    raise SystemExit(0)
entry = {"program": program, "args": args, "stdin": sys.stdin.read()}
with open(os.environ["ACCOUNT_TEST_CALLS"], "a") as log:
    log.write(json.dumps(entry) + "\n")
if program not in {"ssh", "docker"}:
    raise SystemExit(97)
if os.getenv("ACCOUNT_TEST_FAIL_SSH") == "1" and program == "ssh":
    raise SystemExit(71)
if (program == "docker" and "/bootstrap-scripts/verify-staging-test-accounts.py" in args
        and os.getenv("ACCOUNT_TEST_VERIFY_FAIL") == "1"):
    raise SystemExit(1)
'''


class Cursor:
    def __init__(self, value=None):
        self.value = value

    def fetchone(self):
        return self.value


class Connection:
    def __init__(self, *, role_exists=False, schema_exists=False):
        self.statements = []
        self.role_exists, self.schema_exists = role_exists, schema_exists

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        text = statement if isinstance(statement, str) else statement.as_string()
        self.statements.append(text)
        if "FROM pg_roles" in text:
            return Cursor((1,) if self.role_exists else None)
        if "FROM pg_namespace" in text:
            return Cursor((1,) if self.schema_exists else None)
        return Cursor()


class StagingTestAccountsBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="staging-account-boundaries-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home, self.bin = self.base / "home", self.base / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.calls = self.base / "calls.jsonl"
        for name in ("ssh", "docker", "readlink"):
            executable = self.bin / name
            executable.write_text(f"#!{sys.executable}\n" + FAKE_PROGRAM)
            executable.chmod(0o700)
        ssh = self.home / ".ssh"
        ssh.mkdir()
        (ssh / "staging_key").write_text("fake key")
        (ssh / "known_hosts").write_text("fake known host")
        self.env = os.environ | {"HOME": str(self.home), "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                                "ACCOUNT_TEST_CALLS": str(self.calls), "STAGING_SSH_HOST": "fixture.example",
                                "STAGING_SSH_USER": "fixture", "STAGING_SSH_PORT": "22"}
        self.env.pop("STAGING_TEST_ACCOUNTS_JSON", None)
        self.env.pop("ACCOUNT_TEST_FAIL_SSH", None)
        self.env.pop("ACCOUNT_TEST_VERIFY_FAIL", None)

    def events(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def shell(self, name, *arguments, input_text=None):
        return subprocess.run(["bash", str(ROOT / "scripts" / name), *arguments], env=self.env,
                              input=input_text, text=True, capture_output=True, timeout=10)

    def assert_private(self, result):
        output = result.stdout + result.stderr
        self.assertTrue(all(value not in output for value in PASSWORDS.values()), "Credentials appeared in setup output")
        self.assertTrue(all(value not in json.dumps(event["args"])
                            for event in self.events() for value in PASSWORDS.values()), "Credentials appeared in process arguments")

    def env_file(self, *, with_urls=True):
        path = self.base / ".env"
        text = ("# existing deployment must be preserved\nPOSTGRES_PASSWORD=fixture-db-password\n"
                "STAGING_WEB_PORT=8088\nD_M1_TOKEN=fixture-d-m1\nM3_M1_TOKEN=fixture-m3-m1\n"
                "M1_M2_TOKEN=fixture-m2-m1\nM1_CHECKIN_SECRET=fixture-checkin\n")
        if with_urls:
            text += "".join(f"{service.upper()}_DATABASE_URL=postgresql://existing-{service}:fixture@postgres/campus\n"
                            for service in ("m1", "d", "m3"))
        path.write_text(text)
        path.chmod(0o600)
        return path, text

    def test_no_secret_is_no_remote_operation(self):
        self.env.pop("STAGING_SSH_HOST", None)
        result = self.shell("enable-staging-test-accounts-remote.sh")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.events(), [])

    def test_secret_only_reaches_ssh_stdin_and_failure_is_not_swallowed(self):
        self.env["STAGING_TEST_ACCOUNTS_JSON"] = MAPPING
        result = self.shell("enable-staging-test-accounts-remote.sh")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.events()), 1)
        event = self.events()[0]
        self.assertEqual(event["program"], "ssh")
        self.assertEqual(event["stdin"], MAPPING)
        self.assertIn("StrictHostKeyChecking=yes", event["args"])
        self.assertIn("--credentials-stdin", event["args"][-1])
        self.assert_private(result)
        self.env["ACCOUNT_TEST_FAIL_SSH"] = "1"
        rejected = self.shell("enable-staging-test-accounts-remote.sh")
        self.assertNotEqual(rejected.returncode, 0)
        self.assert_private(rejected)

    def test_compose_start_and_verification_do_not_consume_secret_stdin(self):
        deployment = self.home / "campus-resource-staging"
        release = deployment / "releases" / SHA
        (release / "scripts").mkdir(parents=True)
        (release / "scripts/bootstrap-test-accounts.py").write_text("# fake image boundary\n")
        (deployment / "current").symlink_to(release, target_is_directory=True)
        (deployment / ".env").write_text("POSTGRES_PASSWORD=fixture\n")
        result = self.shell("enable-staging-test-accounts.sh", "--course-test-site", "--credentials-stdin", input_text=MAPPING)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events()
        self.assertEqual(len(events), 5)
        bootstrap = [event for event in events if "/bootstrap-scripts/bootstrap-test-accounts.py" in event["args"]]
        self.assertEqual(len(bootstrap), 1)
        self.assertEqual(bootstrap[0]["stdin"], MAPPING)
        api_updates = [index for index, event in enumerate(events) if "up" in event["args"]
                       and {"d-api", "m1-api", "m3-api"}.issubset(event["args"])]
        web_updates = [index for index, event in enumerate(events) if "up" in event["args"] and "web" in event["args"]]
        verification = [index for index, event in enumerate(events)
                        if "/bootstrap-scripts/verify-staging-test-accounts.py" in event["args"]]
        self.assertEqual(len(api_updates), 1)
        self.assertEqual(len(web_updates), 1)
        self.assertEqual(len(verification), 1)
        self.assertLess(events.index(bootstrap[0]), api_updates[0], "New API configuration must be prepared before service startup")
        self.assertLess(api_updates[0], web_updates[0], "Refresh Nginx upstream resolution after the API containers change")
        self.assertLess(web_updates[0], verification[0], "Verify the refreshed Web proxy, not its old upstream addresses")
        web_arguments = events[web_updates[0]]["args"]
        self.assertIn("--force-recreate", web_arguments, "An unchanged Web environment still needs fresh upstream resolution")
        self.assertIn("--no-deps", web_arguments, "Recreating Web must not recreate its API dependencies again")
        self.assertFalse({"d-api", "m1-api", "m3-api"}.intersection(web_arguments))
        self.assertTrue(all(event["stdin"] == "" for event in events if event is not bootstrap[0]))
        self.assert_private(result)
        self.env["ACCOUNT_TEST_VERIFY_FAIL"] = "1"
        rejected = self.shell("enable-staging-test-accounts.sh", "--course-test-site", "--credentials-stdin", input_text=MAPPING)
        self.assertEqual(rejected.returncode, 1)
        additional = self.events()[len(events):]
        self.assertEqual(sum("/bootstrap-scripts/verify-staging-test-accounts.py" in event["args"]
                             for event in additional), 1, "Password-bearing verification must not be retried")
        self.assert_private(rejected)

    def test_existing_urls_passwords_tokens_and_other_configuration_are_preserved(self):
        path, original = self.env_file()
        connection = Connection()
        with patch.object(BOOTSTRAP.psycopg, "connect", return_value=connection):
            BOOTSTRAP.prepare_config(path)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(any("CREATE ROLE" in item or "ALTER ROLE" in item or "CREATE SCHEMA" in item
                             for item in connection.statements), "Existing service configuration must not change database roles")

    def test_missing_url_with_existing_role_or_schema_stops_without_reset(self):
        for exists in ({"role_exists": True}, {"schema_exists": True}):
            path, original = self.env_file(with_urls=False)
            connection = Connection(**exists)
            with patch.object(BOOTSTRAP.psycopg, "connect", return_value=connection):
                with self.assertRaises(BOOTSTRAP.SetupError):
                    BOOTSTRAP.prepare_config(path)
            self.assertEqual(path.read_text(), original)
            self.assertFalse(any("CREATE ROLE" in item or "ALTER ROLE" in item or "CREATE SCHEMA" in item
                                 for item in connection.statements), "Missing connection must not reset an existing role/schema")

    def test_existing_external_identity_and_recovery_candidate_are_not_replaced(self):
        path, original = self.env_file()
        path.write_text(original + "D_IDENTITY_URL=https://formal-identity.invalid\n")
        with patch.object(BOOTSTRAP.psycopg, "connect") as connect:
            with self.assertRaises(BOOTSTRAP.SetupError):
                BOOTSTRAP.prepare_config(path)
            connect.assert_not_called()
        path.write_text(original)
        pending = path.with_name(".env.test-accounts.pending")
        pending.write_text("private-recovery-candidate\n")
        with patch.object(BOOTSTRAP.psycopg, "connect") as connect:
            with self.assertRaises(BOOTSTRAP.SetupError):
                BOOTSTRAP.prepare_config(path)
            connect.assert_not_called()
        self.assertEqual(pending.read_text(), "private-recovery-candidate\n")
        self.assertEqual(path.read_text(), original)

    def test_whole_setup_lock_serializes_configuration_and_activation(self):
        # Run the real main() twice. Only its enable boundary is replaced; all
        # argument parsing and filesystem lock ownership remain real.
        runner = self.base / "lock-probe.py"
        log = self.base / "lock-events.txt"
        runner.write_text("""import importlib.util
import os
from pathlib import Path
import sys
import time
spec = importlib.util.spec_from_file_location('bootstrap', sys.argv.pop(1))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def fake_enable(args):
    with Path(os.environ['ACCOUNT_LOCK_EVENTS']).open('a') as log:
        log.write('begin\\n')
        log.flush()
        time.sleep(0.15)
        log.write('end\\n')
module.enable = fake_enable
raise SystemExit(module.main())
""")
        arguments = [sys.executable, str(runner), str(ROOT / "scripts/bootstrap-test-accounts.py"),
                     "--course-test-site", "--env-file", str(self.base / ".env"), "--output", str(self.base / "accounts")]
        env = self.env | {"ACCOUNT_LOCK_EVENTS": str(log)}
        children = [subprocess.Popen(arguments, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        try:
            for child in children:
                child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.wait()
        self.assertEqual(log.read_text().splitlines(), ["begin", "end", "begin", "end"])


if __name__ == "__main__":
    unittest.main()
