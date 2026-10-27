"""M3-only storage. All writes serialize on a private guard, across processes."""
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from sqlalchemy import (Column, Float, Integer, JSON, MetaData, String, Table,
                        create_engine, select)
from sqlalchemy.pool import StaticPool
from alembic.config import Config
from alembic import command

metadata = MetaData(schema="m3")
orders = Table("work_orders", metadata,
               Column("id", String(64), primary_key=True), Column("data", JSON, nullable=False))
keys = Table("idempotency_keys", metadata,
             Column("actor_id", String(128), primary_key=True),
             Column("key", String(128), primary_key=True),
             Column("request_hash", String(64), nullable=False),
             Column("order_id", String(64), nullable=False))
outbox = Table("outbox", metadata,
               Column("id", String(64), primary_key=True),
               Column("order_id", String(64), nullable=False),
               Column("payload", JSON, nullable=False),
               Column("correlation_id", String(64), nullable=False),
               Column("status", String(20), nullable=False),
               Column("attempts", Integer, nullable=False),
               Column("next_attempt", Float, nullable=False),
               Column("lease_until", Float, nullable=True),
               Column("lease_token", String(64), nullable=True),
               Column("error", String(400), nullable=True),
               Column("retryable", Integer, nullable=False))
guard = Table("transaction_guard", metadata, Column("id", Integer, primary_key=True))


class Database:
    def __init__(self, url):
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        options = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            options.update(connect_args={"check_same_thread": False, "timeout": 30},
                           execution_options={"schema_translate_map": {"m3": None}})
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        # StaticPool in-memory SQLite shares one connection between API/worker threads.
        # The process-local lock supplements (not replaces) database interprocess locking.
        self._write_lock = RLock()

    def migrate(self):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    @contextmanager
    def transaction(self):
        with self._write_lock, self.engine.connect() as connection:
            try:
                if connection.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    connection.begin()
                    connection.execute(select(guard.c.id).where(guard.c.id == 1).with_for_update())
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def close(self):
        self.engine.dispose()
