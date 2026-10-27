"""Explicit course-staging setup inside the existing API container.

Reuse the existing PostgreSQL database/volume. Never reset an existing role's
password or replace a configured business connection. Secrets stay in private
server files; the optional credential mapping is read only from stdin.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import quote

# The script is mounted separately; the API image keeps services in its cwd.
sys.path.insert(0, str(Path.cwd()))

import psycopg
from psycopg import sql


class SetupError(Exception):
    pass


def read_env(path: Path) -> tuple[str, dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise SetupError("Expected an existing regular staging .env file")
    original = path.read_text()
    values = {}
    for line in original.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)", line)
        if not match:
            raise SetupError("Unsupported .env syntax; preserve it and configure manually")
        key, value = match.groups()
        if key in values:
            raise SetupError(f"Duplicate .env key: {key}")
        value = value.strip()
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise SetupError("Unsupported multiline .env value")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return original, values


def render_env(original: str, updates: dict[str, str]) -> str:
    lines, pending = [], dict(updates)
    for line in original.splitlines():
        key = line.split("=", 1)[0].strip()
        if key in pending:
            lines.append(f"{key}={pending.pop(key)}")
        else:
            lines.append(line)
    lines.extend(f"{key}={value}" for key, value in pending.items())
    return "\n".join(lines) + "\n"


def private_file(path: Path, content: str, owner=None):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        if owner is not None and os.geteuid() == 0:
            os.fchown(handle.fileno(), owner.st_uid, owner.st_gid)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def prepare_config(path: Path):
    original, current = read_env(path)
    password = current.get("POSTGRES_PASSWORD", "")
    if not password or any(char in password for char in "\n\r") or "${" in password:
        raise SetupError("Existing POSTGRES_PASSWORD is required, without variable expansion")
    identity = current.get("D_IDENTITY_URL", "").rstrip("/")
    if identity and identity != "http://d-api:3104":
        raise SetupError("An external identity service is configured; do not replace it with test accounts")
    if current.get("D_APP_ENV", "") not in ("", "production", "staging"):
        raise SetupError("Unexpected D_APP_ENV; inspect existing setup before enabling accounts")
    pending = path.with_name(".env.test-accounts.pending")
    if pending.exists() or pending.is_symlink():
        raise SetupError("A previous setup left .env.test-accounts.pending; recover its configuration before retrying")
    updates = {}
    for key in ("D_M1_TOKEN", "M3_M1_TOKEN", "M1_M2_TOKEN", "M1_CHECKIN_SECRET"):
        if not current.get(key):
            updates[key] = secrets.token_hex(32)
    merged = current | updates
    if len({merged[key] for key in ("D_M1_TOKEN", "M3_M1_TOKEN", "M1_M2_TOKEN", "M1_CHECKIN_SECRET")}) != 4:
        raise SetupError("Existing service credentials must be distinct; none were changed")
    committed = False
    pending_created = False
    try:
        with psycopg.connect(host="postgres", port=5432, dbname="campus", user="campus",
                             password=password, connect_timeout=10) as conn:
            # Serialize setup across operators/workflows without modifying data.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('staging:test-account-setup'))")
            missing = []
            for service in ("m1", "d", "m3"):
                key, role = f"{service.upper()}_DATABASE_URL", f"campus_{service}"
                if current.get(key):
                    continue
                if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                    raise SetupError(f"{role} already exists: supply its original {key}; its password was not reset")
                if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (service,)).fetchone():
                    raise SetupError(f"Schema {service} already exists: recover its service connection first")
                missing.append((service, key, role))
            for service, key, role in missing:
                secret = secrets.token_hex(32)
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(secret)))
                conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(sql.Identifier(service), sql.Identifier(role)))
                conn.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(service)))
                conn.execute(sql.SQL("ALTER ROLE {} SET search_path TO {}").format(sql.Identifier(role), sql.Identifier(service)))
                updates[key] = f"postgresql://{role}:{quote(secret, safe='')}@postgres:5432/campus"
            if missing:
                conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            # Keep a private recoverable candidate before committing new roles.
            private_file(pending, render_env(original, updates), path.stat())
            pending_created = True
        committed = True
        os.replace(pending, path)
        os.chmod(path, 0o600)
    except Exception:
        if not committed and pending_created:
            pending.unlink(missing_ok=True)
        raise
    return current | updates


def enable(args):
    credential_input = sys.stdin.read(16385) if args.credentials_stdin else None
    if credential_input is not None:
        # Validate before changing database roles/configuration; never echo data.
        from services.d.test_accounts.seed import unique_object, validate_credentials
        import json
        if len(credential_input) > 16384:
            raise SetupError("Credential input is too large")
        try:
            validate_credentials(json.loads(credential_input, object_pairs_hook=unique_object))
        except Exception:
            raise SetupError("Invalid credential input; expected the four fixed test usernames and strong passwords") from None
    env_file = Path(args.env_file)
    current = prepare_config(env_file)
    env = os.environ | current | {"APP_ENV": "staging", "D_TEST_ACCOUNTS_ENABLED": "1", "D_USE_DEV_IDENTITY": "0"}
    command = [sys.executable, "-m", "services.d.test_accounts.seed", "--output", args.output]
    if args.credentials_stdin:
        command.append("--credentials-stdin")
    result = subprocess.run(command, input=credential_input, text=True, capture_output=True, env=env)
    if result.returncode:
        raise SetupError("Account initialization failed; existing accounts/configuration were preserved. Check seed input and database access")
    # Reuse existing rooms. Only an empty D directory gets synthetic sample data.
    seed_command = """from pathlib import Path
from services.platform import Database
from services.d.seed import seed
db = Database('d')
with db.connection() as conn:
    empty = conn.execute('SELECT count(*) AS n FROM rooms').fetchone()['n'] == 0
if empty:
    seed()
"""
    result = subprocess.run([sys.executable, "-c", seed_command], capture_output=True, env=env)
    if result.returncode:
        raise SetupError("D room initialization failed; no existing room was replaced")
    original, _ = read_env(env_file)
    pending = env_file.with_name(".env.test-accounts.pending")
    private_file(pending, render_env(original, {"D_TEST_ACCOUNTS_ENABLED": "1", "D_APP_ENV": "staging",
                                              "D_IDENTITY_URL": "http://d-api:3104"}), env_file.stat())
    os.replace(pending, env_file)
    print("Test accounts initialized; passwords are only in the private server output file.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--credentials-stdin", action="store_true")
    parser.add_argument("--course-test-site", action="store_true", required=True)
    args = parser.parse_args()
    try:
        # Covers provisioning, secret delivery and final activation, including
        # the interval after the PostgreSQL transaction has released its lock.
        lock_path = Path(args.env_file).parent / ".test-accounts.setup.lock"
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            enable(args)
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        # Driver and validation exceptions can include connection or submitted data.
        print("Test-account setup failed; secrets were not printed. Inspect configuration and PostgreSQL availability.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
