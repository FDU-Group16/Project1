"""One explicit, short database transaction owned by the top-level use case."""

from sqlalchemy.orm import Session, sessionmaker


class M2UnitOfWork:
    """Explicit commit; all other exits roll back. Ports only use/flush session.

    Single-use, not thread-safe. After commit/rollback the transaction is over;
    another use case must create another UoW. Network I/O belongs outside it.
    """

    def __init__(self, factory: sessionmaker[Session]):
        self._factory = factory
        self._session: Session | None = None
        self._entered = False
        self._finished = False

    @property
    def session(self) -> Session:
        if self._session is None or self._finished:
            raise RuntimeError("No active M2 unit of work")
        return self._session

    def __enter__(self) -> "M2UnitOfWork":
        if self._entered:
            raise RuntimeError("M2 unit of work cannot be nested or reused")
        self._entered = True
        session = self._factory()
        try:
            session.begin()
        except BaseException:
            session.close()
            raise
        self._session = session
        return self

    def commit(self) -> None:
        session = self.session
        try:
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            self._finished = True

    def rollback(self) -> None:
        session = self.session
        try:
            session.rollback()
        finally:
            self._finished = True

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        try:
            if not self._finished:
                self._session.rollback()
        finally:
            self._finished = True
            self._session.close()
            self._session = None
