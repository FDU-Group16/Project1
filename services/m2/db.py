"""M2-only synchronous SQLAlchemy infrastructure; importing never connects."""

import os
from collections.abc import Mapping

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

SCHEMA = "m2"


class Base(DeclarativeBase):
    """The only declarative base for M2 models (including future B models)."""

    metadata = MetaData(schema=SCHEMA, naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def parse_database_url(value: str | URL) -> URL:
    """Require explicit PostgreSQL/psycopg configuration, with safe errors."""
    try:
        url = make_url(value)
        valid = (url.drivername == "postgresql+psycopg" and url.host
                 and url.database and url.username and url.password
                 and url.port is not None and 0 < url.port < 65536)
    except (TypeError, ValueError, ArgumentError):
        # SQLAlchemy parser exceptions can contain the secret input.
        raise ValueError("Invalid M2 database configuration") from None
    if not valid:
        raise ValueError("Explicit PostgreSQL psycopg host/port/database/credentials required")
    return url


def database_url_from_env(environ: Mapping[str, str] | None = None) -> URL:
    env = os.environ if environ is None else environ
    if not env.get("M2_DATABASE_URL"):
        raise ValueError("M2_DATABASE_URL is required; no DATABASE_URL fallback")
    return parse_database_url(env["M2_DATABASE_URL"])


def test_database_url_from_env(environ: Mapping[str, str] | None = None) -> URL:
    """Explicit opt-in to the agreed local disposable test database only.

    Query options are disallowed: libpq host/service/options overrides could
    otherwise silently redirect this connection away from the checked target.
    No database is contacted by this check.
    """
    env = os.environ if environ is None else environ
    if env.get("M2_TEST_DATABASE_CONFIRM") != "m2_a_test":
        raise ValueError("Set M2_TEST_DATABASE_CONFIRM=m2_a_test explicitly")
    url = parse_database_url(env.get("M2_TEST_DATABASE_URL", ""))
    try:
        expected_port = int(env["M2_TEST_DATABASE_PORT"])
    except (KeyError, ValueError):
        raise ValueError("Explicit M2_TEST_DATABASE_PORT is required") from None
    if (url.host != "127.0.0.1" or url.port != expected_port
            or url.database != "m2_a_test" or url.username != "m2_a_test"
            or url.query):
        raise ValueError("Refusing database outside the agreed M2 test target")
    return url


def create_m2_engine(url: str | URL) -> Engine:
    return create_engine(parse_database_url(url), pool_pre_ping=True,
                         hide_parameters=True, connect_args={"connect_timeout": 5})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autobegin=False,
                        close_resets_only=False)
