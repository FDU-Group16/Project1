"""M2 application core data; workflow columns await the reviewed policy.

Rows alone are not submitted applications. No runtime route writes this table.
All future application/approval models must use the same Base.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from services.m2.db import Base


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint("attendee_count > 0", name="positive_attendees"),
        CheckConstraint("char_length(purpose) BETWEEN 1 AND 500", name="purpose_length"),
        CheckConstraint("char_length(applicant_id) > 0", name="applicant_id_nonempty"),
        CheckConstraint("char_length(applicant_department_id) > 0", name="department_id_nonempty"),
        CheckConstraint("char_length(room_id) > 0", name="room_id_nonempty"),
        Index("ix_applications_owner_created_id", "applicant_id", "created_at", "application_id"),
    )

    application_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    applicant_id: Mapped[str] = mapped_column(Text)
    applicant_department_id: Mapped[str] = mapped_column(Text)
    room_id: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str] = mapped_column(Text)
    attendee_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationCreationKey(Base):
    """Durable core-create identity; not a submitted-workflow/HTTP receipt."""

    __tablename__ = "application_creation_keys"
    __table_args__ = (
        CheckConstraint("char_length(user_id) > 0", name="user_nonempty"),
        CheckConstraint("action = 'core-create-v1'", name="core_action"),
        CheckConstraint("target = '/applications/core'", name="core_target"),
        CheckConstraint("char_length(key) > 0", name="key_nonempty"),
        CheckConstraint("request_digest ~ '^m2[.]application-create[.]v1:sha256:[0-9a-f]{64}$'",
                        name="digest_format"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    action: Mapped[str] = mapped_column(Text, primary_key=True)
    target: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    request_digest: Mapped[str] = mapped_column(Text)
    application_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("m2.applications.application_id"), unique=True)
