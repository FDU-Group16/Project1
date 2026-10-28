"""M1-owned durable scheduler health and payload-free operational aggregates."""
import os
import re
import socket
from datetime import timedelta
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Depends
from services.platform import Problem, utc_text
from services.m1 import core, dependencies

router = APIRouter(prefix='/api/v1')


def worker_id():
    value = os.getenv('M1_SCHEDULER_ID', socket.gethostname())
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', value):
        raise Problem(503, 'INVALID_SCHEDULER_ID', 'Scheduler ID must contain 1..128 safe characters.')
    return value


def error_code(exc):
    if isinstance(exc, Problem) and re.fullmatch(r'[A-Z0-9_]{1,80}', exc.code):
        return exc.code
    return 'DATABASE_UNAVAILABLE' if isinstance(exc, psycopg.Error) else 'SCHEDULER_CYCLE_FAILED'


def register(instance, stale_seconds):
    run = str(uuid4())
    with core.DB.connection() as conn:
        conn.execute('''INSERT INTO scheduler_workers(worker_id,run_id,state,stale_after_seconds,updated_at)
            VALUES (%s,%s,'STARTING',%s,clock_timestamp()) ON CONFLICT(worker_id) DO UPDATE SET
            run_id=EXCLUDED.run_id,state='STARTING',stale_after_seconds=EXCLUDED.stale_after_seconds,
            last_started_at=NULL,last_finished_at=NULL,last_success_at=NULL,last_error_code=NULL,
            cycles=0,failures=0,updated_at=EXCLUDED.updated_at''', (instance,run,stale_seconds))
    return run


def update(instance, run, state, code=None):
    with core.DB.connection() as conn:
        result = conn.execute('''UPDATE scheduler_workers SET state=%s,updated_at=clock_timestamp(),
            last_started_at=CASE WHEN %s='RUNNING' THEN clock_timestamp() ELSE last_started_at END,
            last_finished_at=CASE WHEN %s IN ('OK','ERROR') THEN clock_timestamp() ELSE last_finished_at END,
            last_success_at=CASE WHEN %s='OK' THEN clock_timestamp() ELSE last_success_at END,
            cycles=cycles+CASE WHEN %s='OK' THEN 1 ELSE 0 END,
            failures=failures+CASE WHEN %s='ERROR' THEN 1 ELSE 0 END,
            last_error_code=CASE WHEN %s='OK' THEN NULL WHEN %s='ERROR' THEN %s ELSE last_error_code END
            WHERE worker_id=%s AND run_id=%s''',
            (state,state,state,state,state,state,state,state,code,instance,run))
        if result.rowcount != 1:
            raise Problem(409, 'SCHEDULER_INSTANCE_REPLACED', 'A newer run owns this scheduler ID.')


def worker_status(row, at):
    if row['state'] == 'STOPPED':
        return 'stopped'
    if row['state'] == 'ERROR' or row['last_error_code']:
        return 'error'
    success = row['last_success_at']
    if success and success <= at < success + timedelta(seconds=row['stale_after_seconds']):
        return 'healthy'
    if not success and at < row['updated_at'] + timedelta(seconds=row['stale_after_seconds']):
        return 'starting'
    return 'stale'


def own_healthy(instance):
    # No migration here: missing configuration/schema/heartbeat must fail closed.
    with core.DB.connection() as conn:
        conn.execute("SET LOCAL statement_timeout='3s'")
        row = conn.execute('SELECT *,clock_timestamp() AS observed_at FROM scheduler_workers WHERE worker_id=%s', (instance,)).fetchone()
    return bool(row and worker_status(row,row['observed_at']) == 'healthy')


def snapshot():
    try:
        with core.DB.connection() as conn:
            conn.execute("SET LOCAL statement_timeout='3s'")
            at = conn.execute('SELECT clock_timestamp() AS at').fetchone()['at']
            rows = conn.execute('SELECT * FROM scheduler_workers ORDER BY updated_at DESC,worker_id').fetchall()
            box = conn.execute('''SELECT count(*) FILTER (WHERE state='PENDING') AS pending,
                count(*) FILTER (WHERE state='PENDING' AND next_attempt_at<=%s) AS due,
                count(*) FILTER (WHERE state='PENDING' AND attempts>0) AS "failedPending",
                count(*) FILTER (WHERE state='ACCEPTED') AS accepted,
                count(*) FILTER (WHERE state='DELIVERED') AS delivered,
                count(*) FILTER (WHERE state='SIMULATED') AS simulated,
                count(*) FILTER (WHERE state='SUPPRESSED') AS suppressed,
                min(created_at) FILTER (WHERE state='PENDING') AS oldest FROM outbox''', (at,)).fetchone()
            overdue = conn.execute("SELECT count(*) AS n FROM reservations WHERE status='RESERVED' AND starts_at+interval '15 minutes'<=%s", (at,)).fetchone()['n']
    except psycopg.Error:
        raise Problem(503,'SCHEDULER_MONITOR_UNAVAILABLE','Scheduler monitoring database is unavailable or not migrated.') from None
    healthy = sum(worker_status(row,at)=='healthy' for row in rows)
    workers = []
    for row in rows[:100]:
        item = {'workerId':row['worker_id'],'status':worker_status(row,at),'cycles':row['cycles'],
                'failures':row['failures'],'lastErrorCode':row['last_error_code'],'staleAfterSeconds':row['stale_after_seconds']}
        for field,column in [('lastStartedAt','last_started_at'),('lastFinishedAt','last_finished_at'),('lastSuccessAt','last_success_at')]:
            item[field] = utc_text(row[column]) if row[column] else None
        workers.append(item)
    oldest = box.pop('oldest')
    box['oldestPendingAt'] = utc_text(oldest) if oldest else None
    status = 'unhealthy' if not healthy else ('degraded' if box['failedPending'] or overdue else 'healthy')
    return {'observedAt':utc_text(at),'dependencyMode':dependencies.dependency_mode(),'status':status,
            'healthyWorkers':healthy,'workers':workers,'outbox':box,'overdueNoShows':overdue}


@router.get('/scheduler')
def scheduler_status(user=Depends(dependencies.identity)):
    dependencies.require(user,'operations:read','room:manage')
    return snapshot()
