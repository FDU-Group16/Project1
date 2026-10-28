"""Application storage against explicitly opted-in private PostgreSQL only."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
import os
import unittest
from uuid import uuid4

from sqlalchemy import delete, insert, select, text
from sqlalchemy.exc import IntegrityError

from services.m2.applications import ApplicationStore
from services.m2.contracts import Actor, ApplicationCreate
from services.m2.db import create_m2_engine, create_session_factory, test_database_url_from_env
from services.m2.models import Application
from services.m2.tests import test_uow_postgres as infrastructure
from services.m2.uow import M2UnitOfWork


@unittest.skipUnless(any(key.startswith("M2_TEST_DATABASE_") for key in os.environ),
                     "PostgreSQL NOT_RUN: provide explicit isolated test configuration")
class ApplicationStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = test_database_url_from_env()
        cls.engine = create_m2_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.connect() as connection:
            identity = connection.execute(text(
                "SELECT current_database(), current_user, host(inet_server_addr()), "
                "inet_server_port(), r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
                "current_setting('server_version_num')::int "
                "FROM pg_roles r WHERE r.rolname = current_user")).one()
            if (identity[:4] != ("m2_a_test", "m2_a_test", "127.0.0.1", cls.url.port)
                    or any(identity[4:7]) or not 180000 <= identity[7] < 190000):
                raise RuntimeError("Refusing unexpected PostgreSQL test identity/version")
        # Use the existing migration helper without inheriting its test cases.
        infrastructure.PostgresUnitOfWorkTests.migrate.__func__(cls)
        cls.factory = create_session_factory(cls.engine)

    def setUp(self):
        token = uuid4().hex
        self.actor = Actor("test-" + token + " /甲", department_id="dept/测试")
        self.other = Actor("other-" + token, department_id="dept/乙")
        self.now = datetime.now(UTC)
        self.data = ApplicationCreate(room_id=" room/测试 ",
                                      start_at=(self.now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                                      end_at=(self.now + timedelta(days=1, hours=2)).isoformat().replace("+00:00", "Z"),
                                      purpose="  合成会议  ", attendee_count=12)
        self.ids = []
        self.store = ApplicationStore()
        self.addCleanup(self.clean_rows)

    def clean_rows(self):
        # Never truncate or delete another run's rows, even in this private DB.
        if self.ids:
            with self.engine.begin() as connection:
                connection.execute(delete(Application).where(Application.application_id.in_(self.ids)))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def new_id(self):
        identity = uuid4()
        self.ids.append(identity)
        return identity

    def add(self, uow, *, actor=None, identity=None, now=None, data=None):
        return self.store.insert(uow=uow, application_id=identity or self.new_id(),
                                 actor=actor or self.actor, data=data or self.data,
                                 now=now or self.now)

    def get(self, identity, actor=None):
        with M2UnitOfWork(self.factory) as uow:
            return self.store.get_mine(uow=uow, actor=actor or self.actor, application_id=identity)

    def test_commit_round_trip_preserves_all_fields_and_returns_detached_utc_snapshot(self):
        with M2UnitOfWork(self.factory) as uow:
            saved = self.add(uow, now=self.now.astimezone(timezone(timedelta(hours=8))))
            self.assertIsNone(self.get(saved.application_id))  # flush is not commit
            uow.commit()
        loaded = self.get(saved.application_id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.applicant_id, self.actor.user_id)
        self.assertEqual(loaded.applicant_department_id, self.actor.department_id)
        self.assertEqual(loaded.room_id, self.data.room_id)
        self.assertEqual(loaded.purpose, "合成会议")
        self.assertEqual(loaded.attendee_count, 12)
        self.assertEqual((loaded.start_at, loaded.end_at), (self.data.start_at, self.data.end_at))
        self.assertEqual(loaded.created_at, self.now)
        self.assertIs(loaded.created_at.tzinfo, UTC)
        with self.assertRaises(FrozenInstanceError):
            loaded.purpose = "changed"

    def test_missing_commit_and_exception_leave_no_partial_application(self):
        with M2UnitOfWork(self.factory) as uow:
            first = self.add(uow)
        self.assertIsNone(self.get(first.application_id))
        with self.assertRaisesRegex(RuntimeError, "synthetic later step failure"):
            with M2UnitOfWork(self.factory) as uow:
                second = self.add(uow)
                raise RuntimeError("synthetic later step failure")
        self.assertIsNone(self.get(second.application_id))

    def test_duplicate_uuid_rolls_back_entire_new_transaction_without_overwrite(self):
        with M2UnitOfWork(self.factory) as uow:
            original = self.add(uow)
            uow.commit()
        with self.assertRaises(IntegrityError):
            with M2UnitOfWork(self.factory) as uow:
                fresh = self.add(uow)
                self.add(uow, identity=original.application_id, actor=self.other)
                uow.commit()
        self.assertIsNone(self.get(fresh.application_id))
        self.assertEqual(self.get(original.application_id), original)

    def test_detail_hides_other_owner_and_unknown_id(self):
        with M2UnitOfWork(self.factory) as uow:
            other = self.add(uow, actor=self.other)
            uow.commit()
        self.assertIsNone(self.get(other.application_id))
        self.assertIsNone(self.get(uuid4()))
        self.assertEqual(self.get(other.application_id, self.other), other)

    def test_owner_filter_precedes_total_and_stable_pagination_including_empty_page(self):
        with M2UnitOfWork(self.factory) as uow:
            own = [self.add(uow).application_id for _ in range(3)]
            for _ in range(4):
                self.add(uow, actor=self.other, now=self.now + timedelta(seconds=1))
            uow.commit()
        with M2UnitOfWork(self.factory) as uow:
            pages = [self.store.list_mine(uow=uow, actor=self.actor, page=i, page_size=2)
                     for i in (1, 2, 3)]
            nobody = self.store.list_mine(uow=uow, actor=Actor("absent-" + uuid4().hex))
        self.assertEqual([p.total for p in pages], [3, 3, 3])
        self.assertEqual([item.application_id for p in pages for item in p.items], sorted(own, reverse=True))
        self.assertEqual(pages[2].items, ())
        self.assertEqual((nobody.items, nobody.total), ((), 0))
        self.assertEqual([p.page for p in pages], [1, 2, 3])

    def test_pagination_orders_newer_records_before_uuid_tiebreaker(self):
        with M2UnitOfWork(self.factory) as uow:
            old = self.add(uow, now=self.now - timedelta(seconds=1))
            new = self.add(uow)
            uow.commit()
        with M2UnitOfWork(self.factory) as uow:
            page = self.store.list_mine(uow=uow, actor=self.actor)
        self.assertEqual([r.application_id for r in page.items], [new.application_id, old.application_id])

    def test_invalid_page_arguments_rejected(self):
        with M2UnitOfWork(self.factory) as uow:
            for page, size in ((0, 20), (-1, 20), (True, 20), (1.5, 20),
                               (1, 0), (1, 101), (1, False), (1, "20")):
                with self.subTest(page=page, size=size), self.assertRaises(ValueError):
                    self.store.list_mine(uow=uow, actor=self.actor, page=page, page_size=size)

    def test_revalidates_input_and_rejects_missing_department_and_naive_clock(self):
        with M2UnitOfWork(self.factory) as uow:
            for kwargs in ({"actor": Actor("test-missing-department")},
                           {"now": self.now.replace(tzinfo=None)},
                           {"data": self.data.model_copy(update={"attendee_count": 0})}):
                with self.subTest(case=next(iter(kwargs))), self.assertRaises(ValueError):
                    self.add(uow, **kwargs)
            uow.commit()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(select(Application.application_id).where(
                Application.application_id.in_(self.ids))).all(), [])

    def test_database_constraints_reject_invalid_direct_writes(self):
        values = dict(applicant_id=self.actor.user_id, applicant_department_id=self.actor.department_id,
                      room_id=self.data.room_id, start_at=self.data.start_at, end_at=self.data.end_at,
                      purpose=self.data.purpose, attendee_count=12, created_at=self.now)
        for invalid in ({"attendee_count": 0}, {"end_at": self.data.start_at},
                        {"purpose": ""}, {"purpose": "x" * 501}, {"applicant_id": ""},
                        {"applicant_department_id": ""}, {"room_id": ""}, {"created_at": None}):
            with self.subTest(column=next(iter(invalid))), self.assertRaises(IntegrityError):
                with self.engine.begin() as connection:
                    connection.execute(insert(Application).values(
                        **(values | invalid | {"application_id": self.new_id()})))


if __name__ == "__main__":
    unittest.main()
