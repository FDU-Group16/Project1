"""0001: durable M3 work orders, create idempotency, and M1 outbox.

Keep this revision immutable after it is applied to a shared environment.
The logical `m3` schema maps to SQLite's main database in local development.
"""

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, UniqueConstraint

metadata = MetaData(schema='m3')
guard = Table('transaction_guard', metadata, Column('id', Integer, primary_key=True))
orders = Table('work_orders', metadata,
    Column('id', String(128), primary_key=True),
    Column('reporter_id', String(128), nullable=False, index=True),
    Column('assignee_id', String(128), nullable=True, index=True),
    Column('created_at', String(32), nullable=False),
    Column('body', Text, nullable=False))
keys = Table('creation_keys', metadata,
    Column('actor_id', String(128), primary_key=True),
    Column('key', String(128), primary_key=True),
    Column('fingerprint', String(64), nullable=False),
    Column('order_id', String(128), nullable=False))
outbox = Table('room_block_outbox', metadata,
    Column('id', String(128), primary_key=True),
    Column('order_id', String(128), nullable=False),
    Column('revision', Integer, nullable=False),
    Column('payload', Text, nullable=False),
    Column('correlation_id', String(128), nullable=False),
    Column('status', String(16), nullable=False),
    Column('attempts', Integer, nullable=False),
    Column('next_attempt_at', String(32), nullable=False, index=True),
    Column('lease_id', String(128), nullable=True),
    Column('last_error', String(80), nullable=True),
    Column('retryable', Integer, nullable=False),
    Column('receipt', Text, nullable=True),
    UniqueConstraint('order_id', 'revision', name='uq_m3_source_revision'))


def upgrade(connection):
    metadata.create_all(connection)
    from sqlalchemy import insert, select
    if connection.execute(select(guard.c.id).where(guard.c.id == 1)).first() is None:
        connection.execute(insert(guard).values(id=1))
