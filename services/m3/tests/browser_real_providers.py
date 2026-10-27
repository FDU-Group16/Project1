"""Local browser acceptance against real M3/M1/D-02 and disposable PostgreSQL.

Supply TEST_M1_DATABASE_URL, TEST_D_DATABASE_URL, TEST_M3_DATABASE_URL and
M3_TEST_ALLOW_RESET=1. NODE_PATH may select an external Playwright installation.
Starts loopback-only APIs/Vite and the explicit synthetic D-01 fixture, runs the
M3 flow plus existing M1/D business and shared-client checks, then stops its own
processes. Never run concurrently with tests clearing the same schemas.
"""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx

from integration_real_providers import (
    ROOT, clear_disposable_m3_data, free_port, identity_provider, sanitized_log_tail,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Vite loopback port; 0 chooses a free port")
    options = parser.parse_args()
    for service in ("M1", "D", "M3"):
        if not os.getenv(f"TEST_{service}_DATABASE_URL", "").startswith("postgresql"):
            raise RuntimeError(f"TEST_{service}_DATABASE_URL must explicitly select disposable PostgreSQL")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for Vite and browser tests")
    vite_script = ROOT / "apps/web/node_modules/vite/bin/vite.js"
    if not vite_script.is_file():
        raise RuntimeError("Install the existing Web dependencies before running browser acceptance")
    tests = (
        ROOT / "services/m3/tests/browser-flow.cjs",
        ROOT / "apps/web/tests/business.browser.cjs",
        ROOT / "apps/web/tests/shared-client.browser.cjs",
    )
    for script in tests:
        if not script.is_file():
            raise RuntimeError(f"Required browser check is missing: {script.relative_to(ROOT)}")
    dependency = subprocess.run([node, "-e", "require('playwright')"], cwd=ROOT,
                                capture_output=True, env=os.environ.copy())
    if dependency.returncode:
        raise RuntimeError("Playwright is unavailable; set NODE_PATH to the external test tooling directory")

    clear_disposable_m3_data()
    ports = {name: free_port() for name in ("d", "m1", "m3")}
    ports["web"] = options.port or free_port()
    env = os.environ.copy()
    env.update({f"{service}_DATABASE_URL": os.environ[f"TEST_{service}_DATABASE_URL"]
                for service in ("M1", "D", "M3")})
    for key in ("D_M1_TOKEN", "M1_M2_TOKEN", "M1_M3_TOKEN", "M1_CHECKIN_SECRET"):
        env[key] = secrets.token_hex(32)
    env.update(APP_ENV="test", M1_USE_DEV_DEPENDENCIES="1", D_USE_DEV_IDENTITY="0",
               D_BASE_URL=f"http://127.0.0.1:{ports['d']}", M3_MODE="production", M3_DIRECTORY_MODE="http",
               M3_M1_MODE="http", M3_M1_BASE_URL=f"http://127.0.0.1:{ports['m1']}",
               M3_M1_TOKEN=env["M1_M3_TOKEN"], M3_WORKER_ENABLED="true", M3_WORKER_INTERVAL_SECONDS="0.1",
               M3_M1_TIMEOUT_SECONDS="2", VITE_USE_DEV_IDENTITY="true", WEB_BUSINESS_TEST="1",
               M1_PROXY_TARGET=f"http://127.0.0.1:{ports['m1']}",
               D_PROXY_TARGET=f"http://127.0.0.1:{ports['d']}",
               M3_PROXY_TARGET=f"http://127.0.0.1:{ports['m3']}")
    processes, logs = [], []
    room_id = None

    def launch(name, command, working_directory, path="/healthz"):
        log = tempfile.TemporaryFile(mode="w+")
        logs.append(log)
        process = subprocess.Popen(command, cwd=working_directory, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
        for _ in range(240):
            if process.poll() is not None:
                raise RuntimeError(f"{name} startup failed (credentials redacted):\n{sanitized_log_tail(log, env)}")
            try:
                response = httpx.get(f"http://127.0.0.1:{ports[name]}{path}", timeout=0.5, trust_env=False)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"{name} readiness timed out")

    def directory_request(method, path, body=None):
        response = httpx.request(method, f"http://127.0.0.1:{ports['d']}{path}",
                                 headers={"Authorization": "Bearer dev-room-admin"},
                                 **({"json": body} if body is not None else {}), timeout=10, trust_env=False)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"D-02 browser fixture request failed: {method} {path} HTTP {response.status_code}")
        return response.json()

    try:
        with identity_provider() as identity_url:
            env.update(D_IDENTITY_URL=identity_url, M3_IDENTITY_BASE_URL=identity_url)
            for service in ("d", "m1", "m3"):
                launch(service, [sys.executable, "-m", "uvicorn", f"services.{service}.main:app", "--host",
                                 "127.0.0.1", "--port", str(ports[service])], ROOT)
            room = directory_request("POST", "/api/v1/rooms", {
                "name": "M3 browser integration " + uuid4().hex[:8], "departmentId": None,
                "openHour": 0, "closeHour": 24, "weekdays": list(range(7)), "active": True,
            })
            room_id = room["id"]
            for number in ("BROWSER-01", "BROWSER-02"):
                directory_request("POST", f"/api/v1/rooms/{room_id}/seats", {"number": number, "hasSocket": True, "active": True})
            env["M3_TEST_ROOM_ID"] = room_id
            launch("web", [node, str(vite_script), "--host", "127.0.0.1", "--port", str(ports["web"]), "--strictPort"],
                   ROOT / "apps/web", path="/")
            base = f"http://127.0.0.1:{ports['web']}"
            print(f"Browser acceptance at {base}: real M3/M1/D-02 with synthetic shared/D-01 test identities.", flush=True)
            for script in tests:
                print(f"Running {script.relative_to(ROOT)}", flush=True)
                completed = subprocess.run([node, str(script), base], cwd=ROOT, env=env, timeout=360)
                if completed.returncode:
                    raise RuntimeError(f"Browser check failed: {script.relative_to(ROOT)}")
            print("PASS real-provider browser checks: M3 workflow/shared login/identity isolation/M1 and M2 routes; "
                  "M1 reservations and D-02 management; shared-client regression. Real D-01 remains unverified.", flush=True)
            # Retire this runner's master-data fixture through its owning public API.
            directory_request("DELETE", f"/api/v1/rooms/{room_id}")
            room_id = None
    finally:
        # Always stop only child processes owned by this run. No broad port kill.
        for process in reversed(processes):
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
    main()
