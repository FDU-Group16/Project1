"""Opt-in real PostgreSQL check; never substitutes SQLite for this evidence.

M3_TEST_POSTGRES_URL must point to a disposable, dedicated M3 test database.
Without that explicit variable the test is reported SKIPPED, not passed.
"""

import os
import unittest
from uuid import uuid4

from sqlalchemy import delete

from services.m3.database import Database
from services.m3.dev_dependencies import DevelopmentDirectory, DevelopmentGateway
from services.m3.migrations.v0001 import orders, outbox, keys
from services.m3.models import CreateOrder
from services.m3.service import WorkOrders
from services.m3.worker import Worker


@unittest.skipUnless(os.environ.get('M3_TEST_POSTGRES_URL'), 'No dedicated PostgreSQL test URL configured')
class PostgresTests(unittest.TestCase):
    def test_migration_replay_transaction_and_persisted_writeback(self):
        db = Database(os.environ['M3_TEST_POSTGRES_URL'])
        order_id = None
        try:
            db.migrate()
            db.migrate()
            db.check_schema()
            directory = DevelopmentDirectory()
            service = WorkOrders(db, directory)
            actor = directory.authenticate('demo-student')
            dispatcher = directory.authenticate('demo-dispatcher')
            technician = directory.authenticate('demo-technician')
            order = service.create(actor, CreateOrder(roomId='room-101', title='PG 集成测试',
                description='合成数据库测试，不是真实报修。', category='other'), str(uuid4()))
            order_id = order['id']
            order = service.command(dispatcher, order_id, 'assign', {
                'version': order['version'], 'assigneeId': technician.id})
            order = service.command(technician, order_id, 'start', {'version': order['version']})
            Worker(service, DevelopmentGateway()).run_once()
            self.assertEqual(service.get(actor, order_id)['status'], 'IN_PROGRESS')
        finally:
            if order_id:
                with db.transaction() as connection:
                    connection.execute(delete(outbox).where(outbox.c.order_id == order_id))
                    connection.execute(delete(keys).where(keys.c.order_id == order_id))
                    connection.execute(delete(orders).where(orders.c.id == order_id))
            db.close()


if __name__ == '__main__':
    unittest.main()
