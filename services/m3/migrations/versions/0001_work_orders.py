"""M3 work orders, creation keys and durable HTTP outbox.

Revision ID: 0001
Revises: none
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema = "m3" if op.get_bind().dialect.name == "postgresql" else None
    op.create_table("work_orders", sa.Column("id", sa.String(64), primary_key=True),
                    sa.Column("data", sa.JSON(), nullable=False), schema=schema)
    op.create_table("idempotency_keys",
                    sa.Column("actor_id", sa.String(128), primary_key=True),
                    sa.Column("key", sa.String(128), primary_key=True),
                    sa.Column("request_hash", sa.String(64), nullable=False),
                    sa.Column("order_id", sa.String(64), nullable=False), schema=schema)
    op.create_table("outbox", sa.Column("id", sa.String(64), primary_key=True),
                    sa.Column("order_id", sa.String(64), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False),
                    sa.Column("correlation_id", sa.String(64), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("next_attempt", sa.Float(), nullable=False),
                    sa.Column("lease_until", sa.Float()), sa.Column("lease_token", sa.String(64)),
                    sa.Column("error", sa.String(400)), sa.Column("retryable", sa.Integer(), nullable=False),
                    schema=schema)
    op.create_index("ix_m3_outbox_due", "outbox", ["status", "next_attempt"], schema=schema)
    op.create_table("transaction_guard", sa.Column("id", sa.Integer(), primary_key=True), schema=schema)
    table = sa.table("transaction_guard", sa.column("id", sa.Integer()), schema=schema)
    op.bulk_insert(table, [{"id": 1}])


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported; restore a verified backup")
