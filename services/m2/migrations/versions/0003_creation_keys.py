"""Atomic retry identity for core storage, separate from formal submission."""

from alembic import op
import sqlalchemy as sa

revision = "0003_creation_keys"
down_revision = "0002_applications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "application_creation_keys",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("request_digest", sa.Text(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "action", "target", "key",
                                name="pk_application_creation_keys"),
        sa.UniqueConstraint("application_id", name="uq_application_creation_keys_application_id"),
        sa.ForeignKeyConstraint(["application_id"], ["m2.applications.application_id"],
                                name="fk_application_creation_keys_application_id_applications"),
        sa.CheckConstraint("char_length(user_id) > 0", name="user_nonempty"),
        sa.CheckConstraint("action = 'core-create-v1'", name="core_action"),
        sa.CheckConstraint("target = '/applications/core'", name="core_target"),
        sa.CheckConstraint("char_length(key) > 0", name="key_nonempty"),
        sa.CheckConstraint("request_digest ~ '^m2[.]application-create[.]v1:sha256:[0-9a-f]{64}$'",
                           name="digest_format"),
        schema="m2",
    )


def downgrade():
    # Removes retry identities: only with explicit data-loss approval.
    op.drop_table("application_creation_keys", schema="m2")
