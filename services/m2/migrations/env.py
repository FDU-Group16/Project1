"""M2-only migration runner. No shared DATABASE_URL or implicit model DDL."""

from alembic import context
from sqlalchemy.schema import CreateSchema

from services.m2.db import Base, SCHEMA, create_m2_engine, database_url_from_env
from services.m2 import models  # noqa: F401 -- register the single M2 metadata

if context.is_offline_mode():
    raise RuntimeError("M2 migrations require an explicitly configured online connection")

engine = create_m2_engine(database_url_from_env())


def include_name(name, type_, parent_names):
    # Autogenerate must not propose drops in another module's namespace.
    if type_ == "schema":
        return name == SCHEMA
    return parent_names.get("schema_name", SCHEMA) == SCHEMA


try:
    with engine.begin() as connection:
        # Bootstrap the namespace before Alembic creates its version table.
        # This and the revision run in the same PostgreSQL transaction.
        connection.execute(CreateSchema(SCHEMA, if_not_exists=True))
        context.configure(connection=connection, target_metadata=Base.metadata,
                          version_table_schema=SCHEMA, include_schemas=True,
                          include_name=include_name)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
