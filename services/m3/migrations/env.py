"""Alembic online migration scoped to the m3 schema."""
from alembic import context
from sqlalchemy import text

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use python -m services.m3.migrate with an explicit database URL")
schema = "m3" if connection.dialect.name == "postgresql" else None
if schema and not connection.execute(text(
    "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'm3')"
)).scalar_one():
    # Even CREATE SCHEMA IF NOT EXISTS checks database-level CREATE before
    # noticing an existing schema. A provisioned M3 schema owner must not need
    # that broader privilege merely to replay its own Alembic migrations.
    connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS m3")
context.configure(connection=connection, version_table_schema=schema)
with context.begin_transaction():
    context.run_migrations()
