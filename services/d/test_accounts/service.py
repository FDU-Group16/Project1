"""PostgreSQL-backed temporary account/session behavior; never a fallback."""
from datetime import timedelta
import hashlib
from services.platform import Problem, utcnow, utc_text
from .security import matches, new_token, token_digest

ACCOUNT_SPECS = (
    ("m3-student", "测试报修人", ("repair:report", "seat:reserve")),
    ("m3-admin", "测试维修管理员", ("repair:dispatch", "repair:report")),
    ("m3-worker1", "测试维修员一", ("repair:work", "repair:report")),
    ("m3-worker2", "测试维修员二", ("repair:work", "repair:report")),
)
LOGIN_WINDOW = timedelta(minutes=15)
ACCOUNT_ATTEMPTS, GLOBAL_ATTEMPTS = 5, 100


def public_user(account):
    return {"id": account["id"], "displayName": account["display_name"],
            "departmentId": account["department_id"], "permissions": list(account["permissions"]),
            "testAccount": True}


def unauthorized():
    return Problem(401, "INVALID_IDENTITY", "身份无效或已过期，请重新登录")


class TestAccountService:
    def __init__(self, database, clock=utcnow):
        self.db, self.clock = database, clock

    def _admit_login(self, username):
        now, denied = self.clock(), False
        buckets = (("all", GLOBAL_ATTEMPTS),
                   ("user:" + hashlib.sha256(username.encode("utf-8", errors="replace")).hexdigest(), ACCOUNT_ATTEMPTS))
        with self.db.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('d:test-account-login-limits'))")
            conn.execute("DELETE FROM test_login_limits WHERE window_start <= %s", (now - LOGIN_WINDOW,))
            for bucket, limit in buckets:
                row = conn.execute("SELECT attempts FROM test_login_limits WHERE bucket=%s", (bucket,)).fetchone()
                if row and row["attempts"] >= limit:
                    denied = True
            if not denied:
                for bucket, _ in buckets:
                    conn.execute("""INSERT INTO test_login_limits(bucket, window_start, attempts) VALUES (%s,%s,1)
                        ON CONFLICT (bucket) DO UPDATE SET attempts=test_login_limits.attempts+1""", (bucket, now))
        # Rejections do not roll back admission counters. They persist across
        # worker/process restarts and don't trust spoofable proxy identity headers.
        if denied:
            raise Problem(429, "LOGIN_RATE_LIMITED", "登录尝试过于频繁，请十五分钟后重试")

    def login(self, username, password):
        username = username.strip().lower()
        self._admit_login(username)
        with self.db.connection() as conn:
            account = (conn.execute("SELECT * FROM test_accounts WHERE username=%s", (username,)).fetchone()
                       if username in {item[0] for item in ACCOUNT_SPECS} else None)
        valid_password = matches(password, account)
        now = self.clock()
        if not valid_password or account["disabled"] or account["expires_at"] <= now:
            raise Problem(401, "INVALID_CREDENTIALS", "账号或密码无效")
        token = new_token()
        with self.db.connection() as conn:
            # Recheck expiry/disable/hash after PBKDF2, without holding a DB lock
            # throughout CPU work. A concurrent revocation wins before issuing.
            current = conn.execute("SELECT * FROM test_accounts WHERE id=%s FOR UPDATE", (account["id"],)).fetchone()
            now = self.clock()
            if (not current or current["disabled"] or current["expires_at"] <= now
                    or current["password_hash"] != account["password_hash"]
                    or current["password_salt"] != account["password_salt"]):
                raise Problem(401, "INVALID_CREDENTIALS", "账号或密码无效")
            expires = min(now + timedelta(hours=2), current["expires_at"])
            conn.execute("DELETE FROM test_sessions WHERE expires_at <= %s OR revoked_at IS NOT NULL", (now,))
            conn.execute("""INSERT INTO test_sessions(token_digest, account_id, created_at, expires_at)
                         VALUES (%s,%s,%s,%s)""", (token_digest(token), current["id"], now, expires))
        return {"accessToken": token, "expiresAt": utc_text(expires), "user": public_user(current)}

    @staticmethod
    def _digest(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise unauthorized()
        digest = token_digest(authorization[7:])
        if digest is None:
            raise unauthorized()
        return digest

    def current(self, authorization):
        digest, now = self._digest(authorization), self.clock()
        with self.db.connection() as conn:
            account = conn.execute("""SELECT a.* FROM test_accounts a JOIN test_sessions s ON s.account_id=a.id
                WHERE s.token_digest=%s AND s.revoked_at IS NULL AND s.expires_at>%s
                AND a.expires_at>%s AND NOT a.disabled""", (digest, now, now)).fetchone()
        if not account:
            raise unauthorized()
        return public_user(account)

    def logout(self, authorization):
        digest, now = self._digest(authorization), self.clock()
        with self.db.connection() as conn:
            updated = conn.execute("""UPDATE test_sessions s SET revoked_at=%s FROM test_accounts a
                WHERE s.token_digest=%s AND s.account_id=a.id AND s.revoked_at IS NULL
                AND s.expires_at>%s AND a.expires_at>%s AND NOT a.disabled RETURNING s.token_digest""",
                (now, digest, now, now)).fetchone()
        if not updated:
            raise unauthorized()

    def technicians(self, authorization):
        actor = self.current(authorization)
        if "repair:dispatch" not in actor["permissions"]:
            raise Problem(403, "PERMISSION_DENIED", "仅维修管理员可访问维修人员目录")
        with self.db.connection() as conn:
            rows = conn.execute("""SELECT * FROM test_accounts WHERE expires_at>%s AND NOT disabled
                AND 'repair:work'=ANY(permissions) ORDER BY username""", (self.clock(),)).fetchall()
        return {"items": [public_user(row) for row in rows]}
