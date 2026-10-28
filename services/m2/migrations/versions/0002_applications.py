"""Application core inputs only; no default workflow or approval policy."""

from alembic import op
import sqlalchemy as sa

revision = "0002_applications"
down_revision = "0001_m2_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "applications",
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("applicant_id", sa.Text(), nullable=False),
        sa.Column("applicant_department_id", sa.Text(), nullable=False),
        sa.Column("room_id", sa.Text(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("attendee_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("application_id", name="pk_applications"),
        sa.CheckConstraint("end_at > start_at", name="time_order"),
        sa.CheckConstraint("attendee_count > 0", name="positive_attendees"),
        sa.CheckConstraint("char_length(purpose) BETWEEN 1 AND 500", name="purpose_length"),
        sa.CheckConstraint("char_length(applicant_id) > 0", name="applicant_id_nonempty"),
        sa.CheckConstraint("char_length(applicant_department_id) > 0", name="department_id_nonempty"),
        sa.CheckConstraint("char_length(room_id) > 0", name="room_id_nonempty"),
        schema="m2",
    )
    op.create_index("ix_applications_owner_created_id", "applications",
                    ["applicant_id", "created_at", "application_id"], schema="m2")


def downgrade():
    # Explicitly destructive: callers must confirm this table's data is disposable.
    op.drop_index("ix_applications_owner_created_id", table_name="applications", schema="m2")
    op.drop_table("applications", schema="m2")
