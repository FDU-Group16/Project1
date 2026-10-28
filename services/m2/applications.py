"""Internal application core storage, not a submit service or public API.

Caller supplies a trusted Actor and validated input. This layer does not prove
identity, room access/capacity or eligibility, or initialize approval tasks.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, true

from services.m2.contracts import Actor, ApplicationCreate
from services.m2.models import Application
from services.m2.uow import M2UnitOfWork


@dataclass(frozen=True, slots=True)
class ApplicationData:
    """Detached core input snapshot; deliberately not the workflow API view."""

    application_id: UUID
    applicant_id: str
    applicant_department_id: str
    room_id: str
    start_at: datetime
    end_at: datetime
    purpose: str
    attendee_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationPage:
    items: tuple[ApplicationData, ...]
    total: int
    page: int
    page_size: int


def _snapshot(row) -> ApplicationData:
    values = {name: getattr(row, name) for name in ApplicationData.__dataclass_fields__}
    for name in ("start_at", "end_at", "created_at"):
        values[name] = values[name].astimezone(UTC)
    return ApplicationData(**values)


class ApplicationStore:
    """Only uses the caller's active UoW; never commits or starts a transaction."""

    def insert(self, *, uow: M2UnitOfWork, application_id: UUID, actor: Actor,
               data: ApplicationCreate, now: datetime) -> ApplicationData:
        if not isinstance(application_id, UUID):
            raise ValueError("application_id must be a UUID")
        if actor.department_id is None:
            raise ValueError("A trusted applicant department is required")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        # Revalidate even model_construct/model_copy inputs at persistence edge.
        data = ApplicationCreate.model_validate(data.model_dump(mode="json"))
        row = Application(application_id=application_id, applicant_id=actor.user_id,
                          applicant_department_id=actor.department_id,
                          room_id=data.room_id, start_at=data.start_at, end_at=data.end_at,
                          purpose=data.purpose, attendee_count=data.attendee_count,
                          created_at=now.astimezone(UTC))
        uow.session.add(row)
        uow.session.flush()
        return _snapshot(row)

    def get_mine(self, *, uow: M2UnitOfWork, application_id: UUID,
                 actor: Actor) -> ApplicationData | None:
        row = uow.session.scalar(select(Application).where(
            Application.application_id == application_id,
            Application.applicant_id == actor.user_id))
        return None if row is None else _snapshot(row)

    def list_mine(self, *, uow: M2UnitOfWork, actor: Actor,
                  page: int = 1, page_size: int = 20) -> ApplicationPage:
        if (type(page) is not int or page < 1 or type(page_size) is not int
                or not 1 <= page_size <= 100):
            raise ValueError("page must be positive; page_size must be 1..100")
        owned = select(Application).where(Application.applicant_id == actor.user_id).cte("owned")
        total = select(func.count().label("total")).select_from(owned).subquery()
        items = (select(owned).order_by(owned.c.created_at.desc(), owned.c.application_id.desc())
                 .offset((page - 1) * page_size).limit(page_size).subquery())
        # One SQL snapshot, including a count row when the requested page is empty.
        rows = uow.session.execute(select(total.c.total, items).select_from(
            total.outerjoin(items, true())).order_by(
                items.c.created_at.desc(), items.c.application_id.desc())).all()
        return ApplicationPage(tuple(_snapshot(row) for row in rows
                                     if row.application_id is not None),
                               rows[0].total, page, page_size)
