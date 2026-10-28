"""Real PostgreSQL tests; opt-in only, no SQLite or mocked transaction engine."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Column, Integer, MetaData, Table, UniqueConstraint, select, text
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from services.m2.db import (Base, SCHEMA, create_m2_engine, create_session_factory,
                            database_url_from_env, test_database_url_from_env)
from services.m2.uow import M2UnitOfWork

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "services/m2/alembic.ini"


class DatabaseConfigurationTests(unittest.TestCase):
    def config(self):
        return {"M2_TEST_DATABASE_CONFIRM": "m2_a_test",
                "M2_TEST_DATABASE_PORT": "55432",
                "M2_TEST_DATABASE_URL":
                    "postgresql+psycopg://m2_a_test:synthetic@127.0.0.1:55432/m2_a_test"}

    def test_missing_explicit_configuration_does_not_use_generic_url(self):
        with self.assertRaises(ValueError):
            database_url_from_env({"DATABASE_URL": self.config()["M2_TEST_DATABASE_URL"]})
        for key in self.config():
            data = self.config()
            del data[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                test_database_url_from_env(data)

    def test_rejects_other_targets_and_libpq_redirects_before_connecting(self):
        original = self.config()["M2_TEST_DATABASE_URL"]
        for invalid in (original.replace("127.0.0.1", "db.example.org"),
                        original.replace("55432", "5432"),
                        original.replace("/m2_a_test", "/shared"),
                        original.replace("m2_a_test:", "postgres:"),
                        original + "?host=elsewhere", original + "?service=shared",
                        original + "?options=-csearch_path=public",
                        original.replace("postgresql+psycopg", "sqlite")):
            with self.subTest(url_kind=invalid.split("?")[-1] if "?" in invalid else "target"):
                with self.assertRaises(ValueError):
                    test_database_url_from_env(self.config() | {"M2_TEST_DATABASE_URL": invalid})

    def test_errors_do_not_include_password(self):
        for value in ("secret-malformed-url", "postgresql+psycopg://u:secret@h:bad/db"):
            with self.assertRaises(ValueError) as error:
                database_url_from_env({"M2_DATABASE_URL": value})
            self.assertNotIn("secret", str(error.exception))

    def test_factory_is_lazy_and_base_is_m2_scoped(self):
        engine = create_m2_engine(test_database_url_from_env(self.config()))
        try:
            self.assertEqual(engine.pool.checkedout(), 0)
            self.assertEqual(Base.metadata.schema, SCHEMA)
        finally:
            engine.dispose()

    def test_migration_chain_has_one_head(self):
        script = ScriptDirectory.from_config(Config(str(CONFIG)))
        self.assertEqual(script.get_heads(), ["0003_creation_keys"])
        self.assertEqual(script.get_revision("0003_creation_keys").down_revision, "0002_applications")
        self.assertEqual(script.get_revision("0002_applications").down_revision, "0001_m2_schema")
        self.assertIsNone(script.get_revision("0001_m2_schema").down_revision)


@unittest.skipUnless(any(key.startswith("M2_TEST_DATABASE_") for key in os.environ),
                     "PostgreSQL NOT_RUN: provide explicit isolated test configuration")
class PostgresUnitOfWorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = test_database_url_from_env()
        cls.engine = create_m2_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)
        # Check actual server identity/privilege before migration or test DDL.
        with cls.engine.connect() as connection:
            identity = connection.execute(text(
                "SELECT current_database(), current_user, host(inet_server_addr()), "
                "inet_server_port(), r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
                "current_setting('server_version_num')::int "
                "FROM pg_roles r WHERE r.rolname = current_user")).one()
            if (identity[:4] != ("m2_a_test", "m2_a_test", "127.0.0.1", cls.url.port)
                    or any(identity[4:7]) or not 180000 <= identity[7] < 190000):
                raise RuntimeError("Refusing unexpected PostgreSQL test identity/version")
        cls.migrate()
        cls.factory = create_session_factory(cls.engine)
        cls.table = Table("uow_probe_" + uuid4().hex, MetaData(schema=SCHEMA),
                          Column("id", Integer, primary_key=True),
                          Column("value", Integer, nullable=False),
                          UniqueConstraint("value", deferrable=True, initially="DEFERRED"))
        cls.table.create(cls.engine)
        cls.addClassCleanup(cls.table.drop, cls.engine)

    @classmethod
    def migrate(cls):
        env = os.environ.copy()
        env["M2_DATABASE_URL"] = cls.url.render_as_string(hide_password=False)
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", str(CONFIG),
                                 "upgrade", "head"], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            # Keep URL/SQL parameters out of assertion output.
            raise RuntimeError(f"M2 migration failed (exit {result.returncode}); rerun with private diagnostics")

    def tearDown(self):
        with self.engine.begin() as connection:
            connection.execute(self.table.delete())
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def rows(self):
        with self.engine.connect() as connection:
            return connection.execute(select(self.table.c.id).order_by(self.table.c.id)).scalars().all()

    def write(self, uow, identity, value=None):
        uow.session.execute(self.table.insert().values(id=identity, value=identity if value is None else value))

    def test_commit_makes_all_writes_visible_together(self):
        with M2UnitOfWork(self.factory) as uow:
            self.write(uow, 1)
            self.write(uow, 2)
            self.assertEqual(self.rows(), [])
            uow.commit()
        self.assertEqual(self.rows(), [1, 2])

    def test_normal_exit_without_commit_rolls_back(self):
        with M2UnitOfWork(self.factory) as uow:
            self.write(uow, 1)
            self.write(uow, 2)
        self.assertEqual(self.rows(), [])

    def test_exception_rolls_back_all_writes_and_propagates(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with M2UnitOfWork(self.factory) as uow:
                self.write(uow, 1)
                self.write(uow, 2)
                raise RuntimeError("synthetic failure")
        self.assertEqual(self.rows(), [])

    def test_failed_commit_rolls_back_deferred_constraint(self):
        with self.assertRaises(IntegrityError):
            with M2UnitOfWork(self.factory) as uow:
                self.write(uow, 1, value=7)
                self.write(uow, 2, value=7)
                uow.commit()
        self.assertEqual(self.rows(), [])
        with M2UnitOfWork(self.factory) as uow:
            self.write(uow, 3)
            uow.commit()
        self.assertEqual(self.rows(), [3])

    def test_explicit_rollback_ends_transaction(self):
        with M2UnitOfWork(self.factory) as uow:
            self.write(uow, 1)
            uow.rollback()
            with self.assertRaises(RuntimeError):
                uow.commit()
        self.assertEqual(self.rows(), [])

    def test_completed_uow_and_retained_session_cannot_be_reused(self):
        uow = M2UnitOfWork(self.factory)
        with self.assertRaises(RuntimeError):
            _ = uow.session
        with uow:
            session = uow.session
            self.write(uow, 1)
            uow.commit()
            with self.assertRaises(RuntimeError):
                _ = uow.session
        with self.assertRaises(RuntimeError):
            uow.__enter__()
        with self.assertRaises(InvalidRequestError):
            session.begin()
        self.assertEqual(self.rows(), [1])

    def test_nested_use_is_rejected_without_losing_outer_transaction(self):
        with M2UnitOfWork(self.factory) as uow:
            self.write(uow, 1)
            with self.assertRaises(RuntimeError):
                uow.__enter__()
            uow.commit()
        self.assertEqual(self.rows(), [1])

    def test_upgrade_is_repeatable_and_version_table_is_m2_only(self):
        self.migrate()
        self.migrate()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT version_num FROM m2.alembic_version")).scalars().all(), ["0003_creation_keys"])
            self.assertIsNone(connection.scalar(text("SELECT to_regclass('public.alembic_version')")))


if __name__ == "__main__":
    unittest.main()
