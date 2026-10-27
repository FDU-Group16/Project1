"""CLI-only browser acceptance using real temporary password accounts and D/M1/M3.

Requires exclusively owned TEST_M1_DATABASE_URL, TEST_D_DATABASE_URL and
TEST_M3_DATABASE_URL PostgreSQL databases whose names contain "test", plus
M3_TEST_ALLOW_RESET=1. Clears only M3 test rows and D temporary identity rows.
Uses no identity fixture and no development authentication adapter. Existing
D-02 seed supplies synthetic public room/seat data through its own seed command.

NODE_PATH must resolve the existing Playwright installation; node must be on
PATH. WEB_BROWSER_CHANNEL defaults to chrome (or use an installed channel).
Evidence goes outside the checkout to 工程伦理/.verification; temporary random
credentials are private and deleted after the run. Never run concurrently with
another test resetting these databases. No server/browser starts on import.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time

import httpx
import psycopg
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[3]
VERIFICATION = ROOT.parents[1] / ".verification"
SERVICES = ("M1", "D", "M3")


def database_url(service):
    value = os.environ.get(f"TEST_{service}_DATABASE_URL", "")
    if not value.startswith("postgresql://"):
        raise RuntimeError(f"Explicit TEST_{service}_DATABASE_URL PostgreSQL URL is required")
    try:
        name = conninfo_to_dict(value).get("dbname", "")
    except psycopg.Error:
        raise RuntimeError(f"TEST_{service}_DATABASE_URL is invalid") from None
    if "test" not in name.casefold():
        raise RuntimeError(f"TEST_{service}_DATABASE_URL database name must contain test")
    return value


def verify_database(connection, service):
    if "test" not in connection.execute("SELECT current_database()").fetchone()[0].casefold():
        raise RuntimeError(f"{service} connected database name must contain test")


def reset_test_rows():
    if os.environ.get("M3_TEST_ALLOW_RESET") != "1":
        raise RuntimeError("M3_TEST_ALLOW_RESET=1 is required for exclusively owned disposable databases")
    # Guard every target before any mutation, including a connection-side name
    # check; URL query parameters must not redirect cleanup into a normal DB.
    for service in SERVICES:
        with psycopg.connect(database_url(service)) as connection:
            verify_database(connection, service)
    for service, sentinel, tables in (
        ("M3", "m3.work_orders", "m3.outbox, m3.idempotency_keys, m3.work_orders"),
        ("D", "d.test_accounts", "d.test_sessions, d.test_accounts, d.test_login_limits"),
    ):
        with psycopg.connect(database_url(service)) as connection:
            verify_database(connection, service)
            if connection.execute("SELECT to_regclass(%s)", (sentinel,)).fetchone()[0]:
                connection.execute("TRUNCATE " + tables)  # Fixed table allowlist; never caller-supplied SQL.


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def redact(text, environment):
    values = [value for key, value in environment.items() if value and any(
        marker in key.upper() for marker in ("DATABASE_URL", "PASSWORD", "TOKEN", "SECRET"))]
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    text = re.sub(r"postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?://[^\s\"'<>]+", "[REDACTED_DATABASE_URL]", text)
    return re.sub(r"https?://[^/\s\"'<>]+@[^\s\"'<>]+", "[REDACTED_CREDENTIAL_URL]", text)


def stop(process):
    if process.poll() is None:
        # Each child has a dedicated process group; no port-wide process kill.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def interrupt_run(_signal, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Vite loopback port; 0 chooses a free port")
    parser.add_argument("--evidence-dir", type=Path, help="New output directory inside 工程伦理/.verification")
    options = parser.parse_args()
    if not 0 <= options.port <= 65535:
        raise RuntimeError("Port must be between 0 and 65535")
    if os.environ.get("M3_TEST_ALLOW_RESET") != "1":
        raise RuntimeError("M3_TEST_ALLOW_RESET=1 is required for exclusively owned disposable databases")
    urls = {service: database_url(service) for service in SERVICES}
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js must be on PATH")
    vite_script = ROOT / "apps/web/node_modules/vite/bin/vite.js"
    tests = [ROOT / "apps/web/tests/test-accounts.browser.cjs", ROOT / "apps/web/tests/shared-client.browser.cjs"]
    if not vite_script.is_file() or not all(script.is_file() for script in tests):
        raise RuntimeError("Install existing Web dependencies and ensure both browser scripts are available")
    result = subprocess.run([node, "-e", "require('playwright')"], cwd=ROOT, env=os.environ.copy(),
                            capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Playwright is unavailable; point NODE_PATH at the existing test tooling")

    tag = datetime.now(timezone.utc).strftime("test-accounts-browser-%Y%m%dT%H%M%SZ-") + secrets.token_hex(3)
    evidence = (options.evidence_dir or VERIFICATION / tag).expanduser().resolve()
    if not evidence.is_relative_to(VERIFICATION.resolve()) or evidence.is_relative_to(ROOT):
        raise RuntimeError("Evidence must be outside the checkout and inside 工程伦理/.verification")
    evidence.mkdir(parents=True, exist_ok=False)
    ports = {name: free_port() for name in ("d", "m1", "m3")}
    ports["web"] = options.port or free_port()
    if len(set(ports.values())) != len(ports):
        raise RuntimeError("Allocated ports collided; retry the runner")
    env = os.environ.copy()
    env.update({f"{service}_DATABASE_URL": value for service, value in urls.items()})
    for key in ("D_M1_TOKEN", "M1_M2_TOKEN", "M1_M3_TOKEN", "M1_CHECKIN_SECRET"):
        env[key] = secrets.token_hex(32)
    d_url, m1_url = f"http://127.0.0.1:{ports['d']}", f"http://127.0.0.1:{ports['m1']}"
    env.update(APP_ENV="test", D_TEST_ACCOUNTS_ENABLED="1", D_USE_DEV_IDENTITY="0", M1_USE_DEV_DEPENDENCIES="0",
               D_BASE_URL=d_url, D_IDENTITY_URL=d_url, M3_IDENTITY_BASE_URL=d_url,
               M3_MODE="production", M3_DIRECTORY_MODE="http", M3_M1_MODE="http",
               M3_M1_BASE_URL=m1_url, M3_M1_TOKEN=env["M1_M3_TOKEN"], M3_WORKER_ENABLED="true",
               M3_WORKER_INTERVAL_SECONDS="0.1", M3_M1_TIMEOUT_SECONDS="2", VITE_USE_DEV_IDENTITY="false",
               M1_PROXY_TARGET=m1_url, D_PROXY_TARGET=d_url, M3_PROXY_TARGET=f"http://127.0.0.1:{ports['m3']}",
               M3_TEST_ROOM_ID="demo-room-public", WEB_TEST_SCREENSHOT_DIR=str(evidence / "screenshots"))
    processes, logs = [], []
    summary = {"passed": False, "identity": "temporary password accounts, no identity fixture",
               "business": "real D-02/M1/M3 HTTP and PostgreSQL; synthetic seeded room",
               "formalD01": "not delivered", "browserChannel": env.get("WEB_BROWSER_CHANNEL", "chrome"), "checks": []}
    reset_done = False

    def run_command(name, command, timeout=60):
        log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        logs.append((name, log))
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        try:
            result = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(process)
            raise RuntimeError(f"{name} timed out") from None
        if result:
            raise RuntimeError(f"{name} failed; see redacted evidence log")

    def launch(name, command, working_directory=ROOT, path="/healthz"):
        log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        logs.append((name, log))
        process = subprocess.Popen(command, cwd=working_directory, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append(process)
        for _ in range(240):
            if process.poll() is not None:
                raise RuntimeError(f"{name} startup failed; see redacted evidence log")
            try:
                if httpx.get(f"http://127.0.0.1:{ports[name]}{path}", timeout=0.5, trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"{name} readiness timed out")

    previous_term = signal.signal(signal.SIGTERM, interrupt_run)
    try:
        reset_test_rows()
        reset_done = True
        with tempfile.TemporaryDirectory(prefix="m3-browser-test-accounts-") as private:
            credentials = Path(private) / "accounts.json"
            # Both seed commands operate through their owning D implementation.
            # These randomly generated credentials are never deployment accounts.
            run_command("seed-directory", [sys.executable, "-m", "services.d.seed"])
            run_command("seed-test-accounts", [sys.executable, "-m", "services.d.test_accounts.seed", "--output",
                                               str(credentials), "--days", "1"])
            if stat.S_IMODE(credentials.stat().st_mode) != 0o600:
                raise RuntimeError("Temporary credential output must have mode 0600")
            data = json.loads(credentials.read_text(encoding="utf-8"))
            for item in data["accounts"]:
                env[f"REDACT_{item['username']}_PASSWORD"] = item["password"]
            env["WEB_TEST_ACCOUNTS_FILE"] = str(credentials)
            for service in ("d", "m1", "m3"):
                launch(service, [sys.executable, "-m", "uvicorn", f"services.{service}.main:app", "--host",
                                 "127.0.0.1", "--port", str(ports[service])])
            context = httpx.get(d_url + "/api/v1/auth/context", timeout=5, trust_env=False)
            if context.status_code != 200 or context.json() != {"mode": "test-accounts"}:
                raise RuntimeError("Real D temporary password provider was not activated")
            m3_context = httpx.get(f"http://127.0.0.1:{ports['m3']}/api/m3/v1/context", timeout=5, trust_env=False).json()
            if not (m3_context.get("mode") == "production" and m3_context.get("directoryMode") == "http"
                    and m3_context.get("businessReady") is True and not m3_context.get("demoIdentities")):
                raise RuntimeError("M3 must use production HTTP adapters without development identities")
            launch("web", [node, str(vite_script), "--host", "127.0.0.1", "--port", str(ports["web"]), "--strictPort"],
                   ROOT / "apps/web", path="/")
            base = f"http://127.0.0.1:{ports['web']}"
            print(f"Running real password-account browser checks at {base}; evidence: {evidence}", flush=True)
            for script in tests:
                name = script.name.removesuffix(".cjs")
                run_command(name, [node, str(script), base], timeout=360)
                summary["checks"].append(str(script.relative_to(ROOT)))
                print(f"PASS {script.relative_to(ROOT)}", flush=True)
            summary["passed"] = True
            print("PASS four password identities, refresh/logout, M3 lifecycle and shared-client regression. "
                  "Temporary credentials will be removed; formal campus D-01 remains unavailable.", flush=True)
    finally:
        for process in reversed(processes):
            stop(process)
        for name, log in logs:
            log.flush()
            log.seek(0)
            (evidence / f"{name}.log").write_text(redact(log.read(), env), encoding="utf-8")
            log.close()
        if reset_done:
            try:
                reset_test_rows()
                summary["cleanup"] = "owned child processes stopped; temporary credentials deleted; M3 test and D identity rows cleared"
            except Exception:
                summary["passed"] = False
                summary["cleanup"] = "database cleanup failed; reset the exclusively owned test databases before reuse"
                raise
            finally:
                (evidence / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            (evidence / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Browser test interrupted; owned children were stopped.") from None
    except Exception as error:
        # SQL/seed failures may contain sensitive values. Keep terminal output
        # limited to our safe errors; details go only through redaction above.
        message = str(error) if type(error) is RuntimeError else type(error).__name__
        raise SystemExit(f"Password-account browser verification failed: {message}") from None
