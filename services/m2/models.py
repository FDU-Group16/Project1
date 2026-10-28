"""M2 application core data; workflow columns await the reviewed policy.

Rows alone are not submitted applications. No runtime route writes this table.
All future application/approval models must use the same Base.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Text, Uuid
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
