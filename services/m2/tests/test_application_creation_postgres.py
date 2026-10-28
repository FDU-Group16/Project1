"""Real PG retry/concurrency tests; no HTTP, identity or approval substitute."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import timedelta
import os
from queue import Queue
import time
import unittest
from uuid import uuid4

from sqlalchemy import delete, event, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from services.m2.application_creation import ApplicationCreationConflict, ApplicationCreationStore
from services.m2.applications import ApplicationStore
from services.m2.idempotency import application_input_digest
from services.m2.models import Application, ApplicationCreationKey
from services.m2.tests import test_applications_postgres as fixtures
from services.m2.uow import M2UnitOfWork


@unittest.skipUnless(any(key.startswith("M2_TEST_DATABASE_") for key in os.environ),
                     "PostgreSQL NOT_RUN: provide explicit isolated test configuration")
class ApplicationCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ApplicationStorageTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.ApplicationStorageTests.setUp(self)
        self.creation = ApplicationCreationStore()
        self.key = "test-key-" + uuid4().hex

    def clean_rows(self):
        # Exact randomly generated test actors; never truncate or sweep other data.
        users = [self.actor.user_id, self.other.user_id]
        with self.engine.begin() as connection:
            connection.execute(delete(ApplicationCreationKey).where(
                ApplicationCreationKey.user_id.in_(users)))
            connection.execute(delete(Application).where(Application.applicant_id.in_(users)))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def save(self, uow, **kwargs):
        return self.creation.save(**(dict(uow=uow, actor=self.actor, data=self.data,
                                          key=self.key, now=self.now) | kwargs))

    def counts(self):
        with self.engine.connect() as connection:
            return tuple(connection.scalar(select(func.count()).select_from(model).where(column.in_(
                [self.actor.user_id, self.other.user_id]))) for model, column in (
                    (Application, Application.applicant_id),
                    (ApplicationCreationKey, ApplicationCreationKey.user_id)))

    def test_committed_retry_replays_canonical_input_across_sessions(self):
        with M2UnitOfWork(self.factory) as uow:
            first = self.save(uow)
            self.assertEqual(self.counts(), (0, 0))  # No hidden commit.
            uow.commit()
        equivalent = self.data.model_copy(update={"purpose": "  合成会议  "})
        with M2UnitOfWork(self.factory) as uow:
            replay = self.save(uow, data=equivalent, now=self.now + timedelta(minutes=1))
            uow.commit()
        self.assertFalse(first.replayed)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.application, first.application)
        self.assertEqual(self.counts(), (1, 1))
        with self.assertRaises(FrozenInstanceError):
            replay.replayed = False

    def test_same_key_changed_input_conflicts_without_overwriting_original(self):
        with M2UnitOfWork(self.factory) as uow:
            first = self.save(uow)
            uow.commit()
        changed = self.data.model_copy(update={"attendee_count": 13})
        with M2UnitOfWork(self.factory) as uow:
            with self.assertRaises(ApplicationCreationConflict) as error:
                self.save(uow, data=changed)
            self.assertNotIn(self.key, str(error.exception))
            self.assertEqual(self.save(uow).application, first.application)
            uow.commit()
        self.assertEqual(self.counts(), (1, 1))

    def test_different_users_and_exact_keys_are_independent(self):
        with M2UnitOfWork(self.factory) as uow:
            own = self.save(uow)
            other = self.save(uow, actor=self.other)
            spaced = self.save(uow, key=" " + self.key)
            self.assertTrue(self.save(uow).replayed)
            self.assertEqual(len({x.application.application_id for x in (own, other, spaced)}), 3)
            self.assertIsNone(ApplicationStore().get_mine(
                uow=uow, actor=self.actor, application_id=other.application.application_id))
            uow.commit()
        self.assertEqual(self.counts(), (3, 3))

    def test_no_commit_or_later_failure_rolls_back_key_and_application(self):
        with M2UnitOfWork(self.factory) as uow:
            self.save(uow)
        self.assertEqual(self.counts(), (0, 0))
        with self.assertRaisesRegex(RuntimeError, "synthetic later step"):
            with M2UnitOfWork(self.factory) as uow:
                self.save(uow)
                raise RuntimeError("synthetic later step")
        self.assertEqual(self.counts(), (0, 0))
        with M2UnitOfWork(self.factory) as uow:
            self.assertFalse(self.save(uow).replayed)
            uow.commit()
        self.assertEqual(self.counts(), (1, 1))

    def race(self, *, first_commits, changed=False):
        ready = Queue()
        marker_id = uuid4()

        def competing_call():
            with M2UnitOfWork(self.factory) as second:
                second.session.execute(text("SET LOCAL statement_timeout = '8s'"))
                # A prior caller-owned write must survive losing the savepoint.
                ApplicationStore().insert(uow=second, application_id=marker_id,
                    actor=self.actor, data=self.data, now=self.now)
                ready.put(second.session.scalar(text("SELECT pg_backend_pid()")))
                try:
                    result = self.save(second, data=(self.data.model_copy(
                        update={"attendee_count": 13}) if changed else self.data))
                except ApplicationCreationConflict:
                    result = "conflict"
                second.commit()
                return result

        with ThreadPoolExecutor(max_workers=1) as executor:
            # Outer transaction exits BEFORE executor joins if an assertion fails.
            with M2UnitOfWork(self.factory) as first:
                original = self.save(first)
                owner_pid = first.session.scalar(text("SELECT pg_backend_pid()"))
                future = executor.submit(competing_call)
                waiter_pid = ready.get(timeout=5)
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with self.engine.connect() as observer:
                        blockers = observer.scalar(text("SELECT pg_blocking_pids(:pid)"),
                                                    {"pid": waiter_pid})
                    if owner_pid in blockers:
                        blocked = True
                        break
                    if future.done():
                        future.result()  # Expose premature DB failure, don't hide it.
                        break
                    time.sleep(0.01)
                self.assertTrue(blocked, "Two real connections must contend on the key")
                if first_commits:
                    first.commit()
                else:
                    first.rollback()
            result = future.result(timeout=10)
        self.assertEqual(self.counts(), (2, 1))  # Winner plus caller marker, no losing candidate.
        with M2UnitOfWork(self.factory) as uow:
            self.assertIsNotNone(ApplicationStore().get_mine(
                uow=uow, actor=self.actor, application_id=marker_id))
        return original, result

    def test_concurrent_same_key_waits_then_replays_committed_winner(self):
        original, result = self.race(first_commits=True)
        self.assertTrue(result.replayed)
        self.assertEqual(result.application, original.application)

    def test_concurrent_waiter_creates_after_first_transaction_rolls_back(self):
        original, result = self.race(first_commits=False)
        self.assertFalse(result.replayed)
        self.assertNotEqual(result.application.application_id, original.application.application_id)

    def test_concurrent_different_input_conflicts_and_keeps_callers_prior_write(self):
        original, result = self.race(first_commits=True, changed=True)
        self.assertEqual(result, "conflict")
        with M2UnitOfWork(self.factory) as uow:
            self.assertEqual(self.save(uow).application, original.application)

    def test_invalid_inputs_and_non_read_committed_fail_explicitly(self):
        with M2UnitOfWork(self.factory) as uow:
            for kwargs in ({"key": ""}, {"now": self.now.replace(tzinfo=None)},
                           {"data": self.data.model_copy(update={"attendee_count": 0})}):
                with self.subTest(case=next(iter(kwargs))), self.assertRaises(ValueError):
                    self.save(uow, **kwargs)
            uow.commit()
        alternate = self.engine.execution_options(isolation_level="REPEATABLE READ")
        from services.m2.db import create_session_factory
        with M2UnitOfWork(create_session_factory(alternate)) as uow:
            with self.assertRaisesRegex(ValueError, "READ COMMITTED"):
                self.save(uow)
        self.assertEqual(self.counts(), (0, 0))

    def test_key_write_failure_propagates_and_removes_candidate_only(self):
        def fail_key_write(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO m2.application_creation_keys"):
                raise RuntimeError("synthetic key write failure")

        with M2UnitOfWork(self.factory) as uow:
            marker_id = uuid4()
            ApplicationStore().insert(uow=uow, application_id=marker_id, actor=self.actor,
                                      data=self.data, now=self.now)
            event.listen(self.engine, "before_cursor_execute", fail_key_write)
            try:
                with self.assertRaisesRegex(RuntimeError, "synthetic key write failure"):
                    self.save(uow)
            finally:
                event.remove(self.engine, "before_cursor_execute", fail_key_write)
            uow.commit()
        self.assertEqual(self.counts(), (1, 0))

    def test_corrupt_key_pointing_to_another_owner_fails_closed(self):
        with M2UnitOfWork(self.factory) as uow:
            self.save(uow)
            other = ApplicationStore().insert(uow=uow, application_id=uuid4(),
                actor=self.other, data=self.data, now=self.now)
            uow.session.execute(update(ApplicationCreationKey).where(
                ApplicationCreationKey.user_id == self.actor.user_id,
                ApplicationCreationKey.key == self.key).values(application_id=other.application_id))
            uow.commit()
        with M2UnitOfWork(self.factory) as uow:
            with self.assertRaisesRegex(RuntimeError, "matching owned application"):
                self.save(uow)
        self.assertEqual(self.counts(), (2, 1))

    def test_database_constraints_reject_duplicate_or_dangling_keys(self):
        with M2UnitOfWork(self.factory) as uow:
            original = self.save(uow)
            uow.commit()
        values = dict(user_id=self.actor.user_id, action="core-create-v1",
                      target="/applications/core", key=self.key,
                      request_digest=application_input_digest(self.data),
                      application_id=original.application.application_id)
        for invalid in ({}, {"key": "other", "application_id": uuid4()},
                        {"key": "other"}, {"request_digest": "bad"},
                        {"action": "submit"}, {"target": "/applications"}, {"key": ""}):
            with self.subTest(columns=tuple(invalid)), self.assertRaises(IntegrityError):
                with self.engine.begin() as connection:
                    connection.execute(insert(ApplicationCreationKey).values(**(values | invalid)))
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as connection:
                connection.execute(delete(Application).where(
                    Application.application_id == original.application.application_id))
        self.assertEqual(self.counts(), (1, 1))


if __name__ == "__main__":
    unittest.main()
