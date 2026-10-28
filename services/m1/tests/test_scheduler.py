"""Real PostgreSQL and independent scheduler processes; no business mocks."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from services.m1 import core, monitoring
from services.m1.main import app
from services.platform import Problem

ROOT=Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.getenv('TEST_M1_DATABASE_URL'),'Requires explicit disposable TEST_M1_DATABASE_URL')
class SchedulerBehavior(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'M1_DATABASE_URL':os.environ['TEST_M1_DATABASE_URL'],
            'APP_ENV':'test','M1_USE_DEV_DEPENDENCIES':'1'})
        self.env.start()
        self.addCleanup(self.env.stop)
        core.migrate()
        with core.DB.connection() as conn:
            conn.execute('TRUNCATE breaches,outbox,provenance,room_blocks,reservations,scheduler_workers')
        self.children=[]
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=2)
            child.stdout.close()

    def wait_for(self,condition,timeout=5):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if condition(): return
            time.sleep(0.03)
        self.fail('Scheduler condition did not become true before deadline')

    def start_worker(self,instance='test-worker',**extra):
        env={**os.environ,'M1_USE_DEV_DEPENDENCIES':'0','D_NOTIFICATION_TOKEN':'','D_AUDIT_TOKEN':'',
             'M1_SCHEDULER_ID':instance,'M1_SCHEDULER_STALE_SECONDS':'1',**extra}
        child=subprocess.Popen([sys.executable,'-m','services.m1.scheduler','--interval','0.05','--failure-limit','2'],
            cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        self.children.append(child)
        return child,env

    def health(self,env):
        return subprocess.run([sys.executable,'-m','services.m1.scheduler','--healthcheck'],cwd=ROOT,
            env=env,capture_output=True,text=True,timeout=7)

    def seed_overdue(self):
        now=core.now(); start=now-timedelta(minutes=16)
        with core.DB.connection() as conn:
            conn.execute('''INSERT INTO reservations(id,user_id,room_id,room_name,seat_id,seat_number,
                starts_at,ends_at,status,created_at,idempotency_key,request_payload)
                VALUES ('private-booking','private-user','test-room','Test','test-seat','01',%s,%s,
                'RESERVED',%s,'test-key',%s)''',(start,now+timedelta(hours=1),now,Jsonb({})))

    def test_worker_restart_fencing_and_failed_cycle_recovery(self):
        run=monitoring.register('one',2)
        self.assertFalse(monitoring.own_healthy('one'))
        monitoring.update('one',run,'RUNNING');monitoring.update('one',run,'OK')
        self.assertTrue(monitoring.own_healthy('one'))
        monitoring.update('one',run,'ERROR','SCHEDULER_CYCLE_FAILED')
        monitoring.update('one',run,'RUNNING')
        self.assertFalse(monitoring.own_healthy('one'))
        monitoring.update('one',run,'OK')
        self.assertTrue(monitoring.own_healthy('one'))
        monitoring.register('one',2)
        self.assertFalse(monitoring.own_healthy('one'))
        with self.assertRaises(Problem) as replaced:
            monitoring.update('one',run,'OK')
        self.assertEqual(replaced.exception.code,'SCHEDULER_INSTANCE_REPLACED')
        core.migrate()  # Replaying migrations retains the operational record.
        self.assertEqual(len(monitoring.snapshot()['workers']),1)

    def test_monitor_authorization_aggregates_and_liveness(self):
        self.seed_overdue()
        with core.DB.connection() as conn:
            for state in ['PENDING','ACCEPTED','DELIVERED','SIMULATED','SUPPRESSED']:
                conn.execute('''INSERT INTO outbox(id,kind,payload,state,attempts,created_at,next_attempt_at)
                    VALUES (%s,'audit',%s,%s,1,clock_timestamp(),clock_timestamp()-interval '1 second')''',
                    (uuid4().hex,Jsonb({'private':'do-not-expose'}),state))
        with TestClient(app) as client:
            self.assertEqual(client.get('/healthz').status_code,200)
            self.assertEqual(client.get('/api/v1/scheduler').status_code,401)
            self.assertEqual(client.get('/api/v1/scheduler',headers={'Authorization':'Bearer dev-student-cs'}).status_code,403)
            result=client.get('/api/v1/scheduler',headers={'Authorization':'Bearer dev-operator'})
        self.assertEqual(result.status_code,200)
        value=result.json()
        self.assertEqual(value['status'],'unhealthy')
        self.assertEqual(value['overdueNoShows'],1)
        self.assertEqual(value['outbox']['pending'],1)
        self.assertEqual(value['outbox']['failedPending'],1)
        self.assertEqual(value['outbox']['accepted'],1)
        self.assertNotIn('private-user',result.text)
        self.assertNotIn('private-booking',result.text)
        self.assertNotIn('do-not-expose',result.text)
        run=monitoring.register('one',2);monitoring.update('one',run,'OK')
        self.assertEqual(monitoring.snapshot()['status'],'degraded')
        with patch.dict(os.environ,{'M1_DATABASE_URL':''}):
            with TestClient(app) as client:
                self.assertEqual(client.get('/healthz').status_code,200)
                self.assertEqual(client.get('/api/v1/scheduler',headers={'Authorization':'Bearer dev-room-admin'}).status_code,503)

    def test_expired_success_is_unhealthy_even_with_another_live_instance(self):
        run=monitoring.register('stale-worker',1)
        monitoring.update('stale-worker',run,'OK')
        with core.DB.connection() as conn:
            conn.execute("UPDATE scheduler_workers SET last_success_at=clock_timestamp()-interval '10 seconds' WHERE worker_id='stale-worker'")
        live=monitoring.register('live-worker',2)
        monitoring.update('live-worker',live,'OK')
        self.assertFalse(monitoring.own_healthy('stale-worker'))
        state=monitoring.snapshot()
        self.assertEqual(state['healthyWorkers'],1)
        self.assertEqual(next(w['status'] for w in state['workers'] if w['workerId']=='stale-worker'),'stale')

    def test_processes_without_http_restart_idempotency_and_stale_detection(self):
        self.seed_overdue()
        first,env=self.start_worker('one')
        second,other_env=self.start_worker('two')
        self.wait_for(lambda:monitoring.snapshot()['healthyWorkers']==2)
        self.wait_for(lambda:monitoring.snapshot()['overdueNoShows']==0)
        self.assertEqual(self.health(env).returncode,0)
        self.assertEqual(self.health(other_env).returncode,0)
        first.terminate();first.wait(timeout=4)
        self.assertEqual(first.returncode,0)
        self.assertFalse(monitoring.own_healthy('one'))
        restarted,env=self.start_worker('one')
        self.wait_for(lambda:monitoring.own_healthy('one'))
        with core.DB.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM breaches').fetchone()['n'],1)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM outbox WHERE id='private-booking:NO_SHOW'").fetchone()['n'],1)
            self.assertEqual(conn.execute("SELECT status FROM reservations WHERE id='private-booking'").fetchone()['status'],'NO_SHOW')
        state=monitoring.snapshot()
        self.assertEqual(state['status'],'degraded')  # Real D delivery unavailable, no fake success.
        self.assertGreater(state['outbox']['failedPending'],0)
        restarted.kill();restarted.wait(timeout=2)
        self.wait_for(lambda:not monitoring.own_healthy('one'),timeout=3)
        self.assertEqual(self.health(env).returncode,1)
        self.assertEqual(self.health(other_env).returncode,0)  # Other worker cannot mask this one.
        logs=first.stdout.read()
        self.assertNotIn('private-user',logs)
        self.assertIn('"dependencyMode": "real"',logs)

    def test_missing_schema_health_and_bounded_cycle_failure(self):
        with core.DB.connection() as conn:
            conn.execute('ALTER TABLE outbox RENAME TO outbox_test_hidden')
        try:
            child,env=self.start_worker()
            child.wait(timeout=5)
            self.assertEqual(child.returncode,1)
            self.assertEqual(self.health(env).returncode,1)
            logs=child.stdout.read()
            self.assertIn('"consecutiveFailures": 2',logs)
            self.assertNotIn('Traceback',logs)
            self.assertNotIn(os.environ['TEST_M1_DATABASE_URL'],logs)
            with self.assertRaises(Problem) as unavailable:
                monitoring.snapshot()
            self.assertEqual(unavailable.exception.status,503)
        finally:
            with core.DB.connection() as conn:
                conn.execute('ALTER TABLE outbox_test_hidden RENAME TO outbox')
        with core.DB.connection() as conn:
            conn.execute('ALTER TABLE scheduler_workers RENAME TO scheduler_test_hidden')
        try:
            self.assertEqual(self.health({**os.environ,'M1_SCHEDULER_ID':'absent'}).returncode,1)
        finally:
            with core.DB.connection() as conn:
                conn.execute('ALTER TABLE scheduler_test_hidden RENAME TO scheduler_workers')


if __name__=='__main__': unittest.main()
