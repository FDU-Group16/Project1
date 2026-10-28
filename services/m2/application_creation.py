"""Idempotent core storage; no public submission, authentication or approvals.

Each call requires fresh authorization by its caller. Keys here must never be
used as successful receipts for a future workflow submission endpoint.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from services.m2.applications import ApplicationData, ApplicationStore
from services.m2.contracts import Actor, ApplicationCreate
from services.m2.idempotency import IdempotencyScope, application_input_digest
from services.m2.models import ApplicationCreationKey
from services.m2.uow import M2UnitOfWork


class ApplicationCreationConflict(ValueError):
    """Same scoped key with a different canonical request; no payload in error."""


@dataclass(frozen=True, slots=True)
class ApplicationSaveResult:
    application: ApplicationData
    replayed: bool


class ApplicationCreationStore:
    """Core insert + key share the caller's READ COMMITTED transaction.

    Never commits/rolls back the outer UoW. A losing concurrent candidate is undone
    with a savepoint only. Database errors propagate; callers bound transaction
    duration and retry the whole use case as appropriate, outside this store.
    """

    def save(self, *, uow: M2UnitOfWork, actor: Actor, data: ApplicationCreate,
             key: str, now: datetime) -> ApplicationSaveResult:
        scope = IdempotencyScope(actor.user_id, "core-create-v1", "/applications/core", key)
        digest = application_input_digest(data)
        if actor.department_id is None:
            raise ValueError("A trusted applicant department is required")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        session = uow.session
        if session.connection().get_isolation_level() != "READ COMMITTED":
            raise ValueError("Core idempotent storage requires READ COMMITTED")
        lookup = select(ApplicationCreationKey).where(
            ApplicationCreationKey.user_id == scope.user_id,
            ApplicationCreationKey.action == scope.action,
            ApplicationCreationKey.target == scope.target,
            ApplicationCreationKey.key == scope.key)
        existing = session.scalar(lookup)
        if existing is not None:
            return self._replay(uow, actor, existing, digest)

        # begin_nested flushes caller pending writes before establishing the
        # savepoint. Those writes remain under the OUTER transaction's control.
        with session.begin_nested() as candidate:
            application = ApplicationStore().insert(
                uow=uow, application_id=uuid4(), actor=actor, data=data, now=now)
            claimed = session.scalar(insert(ApplicationCreationKey).values(
                user_id=scope.user_id, action=scope.action, target=scope.target,
                key=scope.key, request_digest=digest,
                application_id=application.application_id,
            ).on_conflict_do_nothing(
                index_elements=["user_id", "action", "target", "key"]
            ).returning(ApplicationCreationKey.application_id))
            if claimed is not None:
                return ApplicationSaveResult(application, replayed=False)
            candidate.rollback()  # Only remove this call's losing candidate.

        # The competing transaction committed before ON CONFLICT returned.
        # A new READ COMMITTED statement now sees its key and application.
        existing = session.scalar(lookup)
        if existing is None:
            raise RuntimeError("Committed core creation key disappeared")
        return self._replay(uow, actor, existing, digest)

    @staticmethod
    def _replay(uow, actor, existing, digest) -> ApplicationSaveResult:
        if existing.request_digest != digest:
            raise ApplicationCreationConflict("Creation key already used with different input")
        application = ApplicationStore().get_mine(
            uow=uow, actor=actor, application_id=existing.application_id)
        if application is None:
            raise RuntimeError("Core creation key has no matching owned application")
        return ApplicationSaveResult(application, replayed=True)
