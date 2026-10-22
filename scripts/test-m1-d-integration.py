"""Real M1 -> D-02 HTTP + PostgreSQL integration; identity is explicitly synthetic.

Run via test-business.py, which gives this test isolated schemas and credentials.
This does not exercise the unavailable M2/M3 business applications or D-01/03/04.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run():
    dport, mport = free_port(), free_port()
    env = os.environ.copy()
    env.update(APP_ENV='test', M1_USE_DEV_DEPENDENCIES='1', D_USE_DEV_IDENTITY='1',
               D_BASE_URL=f'http://127.0.0.1:{dport}')
    processes = []
    logs = []
    try:
        for service, port in (('d', dport), ('m1', mport)):
            log = tempfile.TemporaryFile(mode='w+')
            logs.append(log)
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', f'services.{service}.main:app',
                                        '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(f'{service} failed to start: {log.read()}')
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/healthz', timeout=0.5).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                raise RuntimeError(f'{service} readiness timed out')

        def request(service, method, path, token='dev-student-cs', expected=200, **kwargs):
            port = dport if service == 'd' else mport
            headers = {'Authorization': f'Bearer {token}', **kwargs.pop('headers', {})}
            response = httpx.request(method, f'http://127.0.0.1:{port}{path}', headers=headers, timeout=10, **kwargs)
            assert response.status_code == expected, (method, path, response.status_code, response.text)
            return response.json()

        room_body = {'name': 'HTTP integration ' + uuid4().hex[:8], 'departmentId': None,
                     'openHour': 0, 'closeHour': 24, 'weekdays': list(range(7)), 'active': True}
        room = request('d', 'POST', '/api/v1/rooms', 'dev-room-admin', expected=201, json=room_body)
        room_id = room['id']
        seat = request('d', 'POST', f'/api/v1/rooms/{room_id}/seats', 'dev-room-admin', expected=201,
                       json={'number': 'HTTP-01', 'hasSocket': True, 'active': True})
        private = request('d', 'POST', '/api/v1/rooms', 'dev-room-admin', expected=201,
                          json={**room_body, 'departmentId': 'ee'})
        request('d', 'GET', '/api/v1/rooms/' + private['id'], expected=403)
        assert private['id'] not in [r['id'] for r in request('d', 'GET', '/api/v1/rooms')['items']]
        start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
        def stamp(value):
            return value.isoformat().replace('+00:00', 'Z')
        interval = {'startsAt': stamp(start), 'endsAt': stamp(start + timedelta(hours=1))}
        query = {**interval, 'roomId': room_id, 'hasSocket': 'true'}
        seats = request('m1', 'GET', '/api/v1/seats', params=query)['items']
        assert seat['id'] in [item['id'] for item in seats]
        booking = {**interval, 'roomId': room_id, 'seatId': seat['id']}
        key = str(uuid4())
        created = request('m1', 'POST', '/api/v1/reservations', json=booking, headers={'Idempotency-Key': key})
        replay = request('m1', 'POST', '/api/v1/reservations', json=booking, headers={'Idempotency-Key': key})
        assert replay['id'] == created['id']
        request('m1', 'GET', '/api/v1/reservations/' + created['id'], 'dev-student-ee', expected=404)
        request('m1', 'POST', '/api/v1/reservations', 'dev-student-ee', expected=409,
                json=booking, headers={'Idempotency-Key': str(uuid4())})
        block = {**interval, 'roomId': room_id, 'revision': 1, 'status': 'ACTIVE'}
        source = str(uuid4())
        request('m1', 'PUT', '/internal/v1/room-blocks/m2/' + source, os.environ['M1_M2_TOKEN'], expected=409, json=block)
        for suffix in ('a', 'b'):
            request('m1', 'PUT', '/internal/v1/room-blocks/m3/' + source + suffix, os.environ['M1_M3_TOKEN'], json=block)
        # M3 does not silently cancel pre-existing student reservations.
        assert request('m1', 'GET', '/api/v1/reservations/' + created['id'])['status'] == 'RESERVED'
        request('m1', 'POST', '/api/v1/reservations/' + created['id'] + '/cancel')
        request('m1', 'PUT', '/internal/v1/room-blocks/m3/' + source + 'a', os.environ['M1_M3_TOKEN'],
                json={**block, 'revision': 2, 'status': 'RELEASED'})
        assert request('m1', 'GET', '/api/v1/seats', params=query)['items'] == []
        request('m1', 'PUT', '/internal/v1/room-blocks/m3/' + source + 'b', os.environ['M1_M3_TOKEN'],
                json={**block, 'revision': 2, 'status': 'RELEASED'})
        assert request('m1', 'GET', '/api/v1/seats', params=query)['items']
        request('m1', 'PUT', '/internal/v1/room-blocks/m3/' + source + 'b', os.environ['M1_M3_TOKEN'], expected=409, json=block)
        provenance = request('m1', 'GET', f'/api/v1/rooms/{room_id}/provenance', 'dev-operator')['items']
        assert {'M1', 'M3'} <= {item['sourceSystem'] for item in provenance}

        def compete(token):
            return httpx.post(f'http://127.0.0.1:{mport}/api/v1/reservations', json=booking,
                              headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': str(uuid4())}, timeout=10).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(compete, ('dev-student-cs', 'dev-student-ee'))) == [200, 409]

        # Credentials enforce schema separation, beyond an application convention.
        for service, other, table in (('M1', 'd', 'rooms'), ('D', 'm1', 'reservations')):
            try:
                with psycopg.connect(os.environ[f'{service}_DATABASE_URL']) as conn:
                    conn.execute(f'SELECT * FROM {other}.{table} LIMIT 1')
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError('Service role can access another schema')

        processes[0].terminate()
        processes[0].wait(timeout=5)
        request('m1', 'GET', '/api/v1/seats', expected=503, params={**query, 'startsAt': stamp(start + timedelta(hours=3)), 'endsAt': stamp(start + timedelta(hours=4))})
        print('PASS real D-02 -> M1 HTTP: CRUD, department/owner scope, replay, concurrent booking, multi-source writeback, schema isolation and provider outage. Identity remains a development substitute.')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()


if __name__ == '__main__':
    run()
