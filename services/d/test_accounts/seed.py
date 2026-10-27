"""Idempotently seed four temporary accounts and deliver credentials privately."""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import psycopg
from services.platform import Database, Problem, utcnow, utc_text
from . import enabled
from .security import ITERATIONS, matches, new_password, password_record
from .service import ACCOUNT_SPECS, public_user

USERNAMES = {item[0] for item in ACCOUNT_SPECS}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate credential field")
        result[key] = value
    return result


def validate_credentials(values):
    if not isinstance(values, dict) or set(values) != USERNAMES:
        raise ValueError("Credential input must contain exactly the four test usernames")
    if not all(isinstance(value, str) and 20 <= len(value) <= 128
               and all(33 <= ord(char) <= 126 for char in value) for value in values.values()):
        raise ValueError("Test passwords must be 20-128 printable non-space ASCII characters")
    if len(set(values.values())) != len(values):
        raise ValueError("Each test account requires its own independent password")
    return values


def read_private_output(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
            raise ValueError("Existing credential output must be an owned regular file with mode 0600")
        value = stream.read(65537)
        if len(value) > 65536:
            raise ValueError("Credential output is too large")
        data = json.loads(value, object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or data.get("mode") != "test-accounts"
            or not isinstance(data.get("accounts"), list)):
        raise ValueError("Invalid private credential output")
    records = {}
    for record in data["accounts"]:
        if (not isinstance(record, dict) or not isinstance(record.get("username"), str)
                or record["username"] in records
                or set(record) != {"username", "password", "expiresAt", "user"}
                or not isinstance(record["expiresAt"], str) or not isinstance(record["user"], dict)):
            raise ValueError("Invalid private account record")
        records[record.get("username")] = record
    validate_credentials({name: record.get("password") for name, record in records.items()})
    return records


def write_private_output(path, payload):
    # Write before DB commit. If commit fails, a retry can reuse this file's
    # generated passwords; never commit accounts whose only password was lost.
    descriptor, temporary = tempfile.mkstemp(prefix=".test-accounts-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # The seed's PostgreSQL advisory lock serializes concurrent invocations.
        # Never overwrite an existing secret file, including a new symlink.
        os.link(temporary, path, follow_symlinks=False)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        os.unlink(temporary)


def seed(output, days=7, *, credentials=None, database=None, clock=utcnow):
    if not enabled():
        raise ValueError("Test account seeding must be explicitly enabled")
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError("Account lifetime must be 1-30 days")
    supplied = validate_credentials(credentials) if credentials is not None else None
    path = Path(output).expanduser().absolute()
    repository = Path(__file__).resolve().parents[3]
    resolved = path.parent.resolve() / path.name
    if resolved.is_relative_to(repository):
        raise ValueError("Store credential output outside the source checkout")
    if not path.parent.is_dir():
        raise ValueError("Create the private output directory before seeding")
    database = database or Database("d")
    database.migrate(Path(__file__).parents[1] / "migrations")
    entries, created = [], 0
    with database.connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('d:test-account-seed'))")
        previous = read_private_output(path)
        for username, display_name, permissions in ACCOUNT_SPECS:
            account = conn.execute("SELECT * FROM test_accounts WHERE username=%s FOR UPDATE", (username,)).fetchone()
            saved = previous[username] if previous else None
            password = supplied[username] if supplied else saved["password"] if saved else None
            if saved and supplied and password != saved["password"]:
                raise ValueError("Supplied credentials do not match the existing private output")
            if account:
                if password is None or not matches(password, account):
                    raise ValueError("Existing account password must match; automatic reset is forbidden")
            else:
                password = password or new_password()
                now = clock()
                expires = (datetime.fromisoformat(saved["expiresAt"].replace("Z", "+00:00"))
                           if saved else now + timedelta(days=days))
                if expires.tzinfo is None or not now < expires <= now + timedelta(days=30):
                    raise ValueError("Private output lifetime cannot be restored without extending it")
                salt, digest = password_record(password)
                # A file left by an interrupted transaction reuses its original
                # secret, while no existing database account is ever modified.
                account = conn.execute("""INSERT INTO test_accounts(id,username,display_name,department_id,
                    permissions,password_salt,password_hash,password_iterations,created_at,expires_at)
                    VALUES (%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    ("test-" + username, username, display_name, list(permissions), salt, digest,
                     ITERATIONS, now, expires)).fetchone()
                created += 1
            entry = {"username": username, "password": password,
                     "expiresAt": utc_text(account["expires_at"]), "user": public_user(account)}
            if saved and saved != entry:
                raise ValueError("Existing private output differs from the account; no data was reset")
            entries.append(entry)
        if previous is None:
            write_private_output(path, {"mode": "test-accounts", "accounts": entries})
    return {"created": created, "existing": len(entries) - created}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Private 0600 credential file outside the checkout")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--credentials-stdin", action="store_true", help="Read exactly four username/password pairs as JSON from stdin")
    options = parser.parse_args()
    try:
        credentials = None
        if options.credentials_stdin:
            raw = sys.stdin.buffer.read(65537)
            if len(raw) > 65536:
                raise ValueError("Credential input is too large")
            credentials = json.loads(raw, object_pairs_hook=unique_object)
        result = seed(options.output, options.days, credentials=credentials)
    except (ValueError, OSError, RuntimeError, Problem, psycopg.Error):
        # Database/JSON exceptions can include submitted data; never echo them.
        raise SystemExit("Test account seed failed. Check activation, database access, private output and matching credentials; existing accounts were not reset.") from None
    print(f"Test account seed complete: {result['created']} created, {result['existing']} preserved; credentials are in the private output file.")


if __name__ == "__main__":
    main()
