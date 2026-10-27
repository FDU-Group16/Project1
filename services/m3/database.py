"""M3-only persistence and versioned migrations; no cross-service table access."""

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from threading import RLock

from sqlalchemy import Column, MetaData, String, Table, create_engine, insert, select, text
from sqlalchemy.pool import StaticPool

from .migrations import v0001

version_metadata = MetaData(schema='m3')
versions = Table('schema_versions', version_metadata,
                 Column('version', String(32), primary_key=True),
                 Column('checksum', String(64), nullable=False))
MIGRATIONS = [('0001', v0001)]


class Database:
    def __init__(self, url: str, *, allow_sqlite: bool = False):
        if url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        self.sqlite = url.startswith('sqlite:')
        if self.sqlite and not allow_sqlite:
            raise ValueError('SQLite is restricted to explicit development/test mode')
        if not self.sqlite and not url.startswith('postgresql+psycopg://'):
            raise ValueError('M3_DATABASE_URL must use PostgreSQL (or development SQLite)')
        options = {'pool_pre_ping': True}
        if self.sqlite:
            options['connect_args'] = {'check_same_thread': False, 'timeout': 30}
            if ':memory:' in url or url in ('sqlite://', 'sqlite:///'):
                options['poolclass'] = StaticPool
        self.engine = create_engine(url, **options).execution_options(
            schema_translate_map={'m3': None if self.sqlite else 'm3'})
        self.local_lock = RLock()

    @contextmanager
    def transaction(self, *, migrating=False):
        # SQLite BEGIN IMMEDIATE also serializes different processes. Postgres
        # locks one M3 guard row; domain operations are small, network is outside.
        with self.local_lock, self.engine.connect() as connection:
            if self.sqlite:
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                connection.begin()
                if migrating:
                    connection.execute(text('SELECT pg_advisory_xact_lock(7030001)'))
                else:
                    connection.execute(select(v0001.guard).where(
                        v0001.guard.c.id == 1).with_for_update()).one()
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextmanager
    def read(self):
        with self.local_lock, self.engine.connect() as connection:
            yield connection

    def migrate(self):
        with self.transaction(migrating=True) as connection:
            if not self.sqlite:
                connection.execute(text('CREATE SCHEMA IF NOT EXISTS m3'))
            version_metadata.create_all(connection)
            applied = dict(connection.execute(select(versions)).all())
            unknown = set(applied) - {v for v, _ in MIGRATIONS}
            if unknown:
                raise RuntimeError('Database schema is newer than this application')
            for version, module in MIGRATIONS:
                digest = sha256(Path(module.__file__).read_bytes()).hexdigest()
                if version in applied:
                    if applied[version] != digest:
                        raise RuntimeError(f'Migration {version} checksum changed')
                    continue
                module.upgrade(connection)
                connection.execute(insert(versions).values(version=version, checksum=digest))

    def check_schema(self):
        with self.read() as connection:
            applied = dict(connection.execute(select(versions)).all())
        expected = {v: sha256(Path(m.__file__).read_bytes()).hexdigest() for v, m in MIGRATIONS}
        if applied != expected:
            raise RuntimeError('M3 migrations must be applied before starting this release')

    def close(self):
        self.engine.dispose()
