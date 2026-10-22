"""Technical PostgreSQL, time and HTTP error primitives; no business calls."""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


def install_errors(app: FastAPI):
    @app.exception_handler(Problem)
    async def problem_handler(request: Request, exc: Problem):
        return JSONResponse(status_code=exc.status, media_type="application/problem+json", content={
            "type": "about:blank", "title": exc.code, "status": exc.status,
            "code": exc.code, "detail": exc.detail,
        })

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Do not echo passwords, tokens, codes or submitted personal data.
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        return await problem_handler(request, Problem(422, "INVALID_REQUEST", f"Invalid fields: {fields}"))

    @app.exception_handler(psycopg.OperationalError)
    async def database_handler(request: Request, exc: Exception):
        return await problem_handler(request, Problem(503, "DATABASE_UNAVAILABLE", "Database is temporarily unavailable"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Database:
    """Each service connects with its own login and search_path.

    Schema/role provisioning is separate. The migration account may own its
    schema; runtime credentials must never access another service's schema.
    """
    def __init__(self, service: str):
        if service not in {"m1", "d"}:
            raise ValueError("Unsupported service")
        self.service = service

    @property
    def configured(self) -> bool:
        return bool(os.getenv(f"{self.service.upper()}_DATABASE_URL"))

    @contextmanager
    def connection(self):
        dsn = os.getenv(f"{self.service.upper()}_DATABASE_URL")
        if not dsn:
            raise Problem(503, "DATABASE_NOT_CONFIGURED", "Service database is not configured")
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            conn.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(self.service)))
            conn.execute("SET TIME ZONE 'UTC'")
            yield conn

    def migrate(self, directory: str | Path):
        with self.connection() as conn:
            # Serialize migration startup across workers without a global lock.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{self.service}:migrations",))
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            for path in sorted(Path(directory).glob("*.sql")):
                exists = conn.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (path.name,)).fetchone()
                if not exists:
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (path.name,))
