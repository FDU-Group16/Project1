"""Password and bearer primitives. No password or raw bearer is persisted."""
import hashlib
import hmac
import re
import secrets

ITERATIONS = 600000


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8", errors="replace"), salt, ITERATIONS, dklen=32)


def new_password():
    return secrets.token_urlsafe(24)


def password_record(password):
    salt = secrets.token_bytes(32)
    return salt, password_hash(password, salt)


def matches(password, record):
    # Unknown users perform the same expensive derivation. The public dummy salt
    # isn't an account credential; its comparison can never grant a login.
    salt = bytes(record["password_salt"]) if record else bytes(32)
    expected = bytes(record["password_hash"]) if record else bytes(32)
    calculated = password_hash(password, salt)
    equal = hmac.compare_digest(calculated, expected)
    return bool(record and record["password_iterations"] == ITERATIONS and equal)


def new_token():
    return secrets.token_urlsafe(32)


def token_digest(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    return hashlib.sha256(token.encode("ascii")).digest()
