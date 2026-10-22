"""Start each empty API and verify its real HTTP health response."""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SERVICES = (("m1", 3911), ("m2", 3912), ("m3", 3913), ("d", 3914))


def check_service(name: str, port: int) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            f"services.{name}.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited early: {process.stdout.read()}")
            try:
                with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as response:
                    body = json.load(response)
                    if (
                        response.status == 200
                        and body.get("service") == f"{name}-api"
                        and body.get("status") == "ok"
                    ):
                        print(f"{name}-api: health check passed")
                        return
            except (URLError, TimeoutError, json.JSONDecodeError):
                time.sleep(0.1)
        raise RuntimeError(f"{name} did not pass health check")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()


for service_name, service_port in SERVICES:
    check_service(service_name, service_port)
