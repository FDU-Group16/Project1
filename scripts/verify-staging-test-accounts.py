"""Read private credentials and verify the existing Web proxy without logging them."""
import json
from pathlib import Path
import sys

import httpx


def ready():
    # Exit 75 only before any password login. Retrying credential-bearing
    # probes would consume the deliberate per-account login attempt limit.
    try:
        with httpx.Client(base_url="http://web", timeout=5, trust_env=False) as client:
            for path in ("http://d-api:3104/healthz", "http://m1-api:3101/healthz", "/api/m3/v1/context"):
                client.get(path).raise_for_status()
    except Exception:
        print("Waiting for API startup and the Web proxy.", file=sys.stderr)
        return False
    return True


def verify():
    accounts = json.loads(Path("/private-test-accounts.json").read_text())["accounts"]
    with httpx.Client(base_url="http://web", timeout=10, trust_env=False, follow_redirects=False) as client:
        context = client.get("/api/m3/v1/context")
        context.raise_for_status()
        if context.json().get("businessReady") is not True:
            raise ValueError("M3 is not configured")
        for account in accounts:
            response = client.post("/api/d/api/v1/auth/login", json={
                "username": account["username"], "password": account["password"]})
            response.raise_for_status()
            session = response.json()
            if session["user"].get("testAccount") is not True:
                raise ValueError("Expected an explicit test account")
            headers = {"Authorization": "Bearer " + session["accessToken"]}
            try:
                for path in ("/api/d/api/v1/auth/me", "/api/m3/v1/me", "/api/m3/v1/rooms", "/api/m3/v1/work-orders"):
                    client.get(path, headers=headers).raise_for_status()
            finally:
                client.post("/api/d/api/v1/auth/logout", headers=headers).raise_for_status()
            if client.get("/api/d/api/v1/auth/me", headers=headers).status_code != 401:
                raise ValueError("Logout did not revoke the session")


if __name__ == "__main__":
    if not ready():
        sys.exit(75)
    try:
        verify()
    except Exception:
        # HTTP errors can carry credential-bearing request objects. Keep all
        # bodies, headers, URLs, and driver details out of deployment output.
        print("Waiting for password login, session revocation and M3 business access.", file=sys.stderr)
        sys.exit(1)
    print("Four test roles verified through the Web proxy; no credentials logged.")
