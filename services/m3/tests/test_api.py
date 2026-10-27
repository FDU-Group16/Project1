"""M3 HTTP tests start actual Uvicorn processes, with only providers substituted."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]


class Server:
    def __init__(self, mode='development'):
        self.temp = tempfile.TemporaryDirectory()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        env = {key: value for key, value in os.environ.items() if not key.startswith('M3_')}
        if mode == 'development':
            env.update(M3_MODE='development', M3_M1_MODE='stub',
                       M3_DATABASE_URL='sqlite:///' + str(Path(self.temp.name) / 'http.db'),
                       M3_WORKER_INTERVAL_SECONDS='0.05')
        elif mode == 'production':
            env['M3_MODE'] = 'production'
        self.output = open(Path(self.temp.name) / 'server.log', 'w+')
        self.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'services.m3.main:app',
            '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env,
            stdout=self.output, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if self.process.poll() is not None:
                    self.output.seek(0)
                    raise RuntimeError(self.output.read())
                try:
                    if self.request('GET', '/healthz')[0] == 200:
                        return
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(0.05)
            raise RuntimeError('M3 HTTP test server did not start')
        except BaseException:
            self.close()
            raise

    def request(self, method, path, body=None, token=None, key=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if key:
            headers['Idempotency-Key'] = key
        request = Request(self.url + path, method=method, headers=headers,
                          data=json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.output.close()
        self.temp.cleanup()


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def request(self, method, path, body=None, token='demo-student', key=None):
        return self.server.request(method, '/api/m3/v1' + path, body, token, key)

    def create(self):
        status, order = self.request('POST', '/work-orders', {'roomId': 'room-101',
            'title': '网络故障', 'description': '该房间无法联网。', 'category': 'network'}, key=str(uuid4()))
        self.assertEqual(status, 201, order)
        return order

    def command(self, order, action, token='demo-student', **fields):
        status, result = self.request('POST', f'/work-orders/{order["id"]}/{action}',
                                     {'version': order['version'], **fields}, token)
        self.assertEqual(status, 200, result)
        return result

    def wait_status(self, order, expected):
        for _ in range(100):
            status, order = self.request('GET', '/work-orders/' + order['id'])
            self.assertEqual(status, 200)
            if order['status'] == expected:
                return order
            time.sleep(0.05)
        self.fail(f'Expected {expected}, got {order}')

    def test_real_http_complete_flow(self):
        order = self.create()
        status, context = self.request('GET', '/context', token=None)
        self.assertEqual((status, context['mode'], context['dependencyMode']), (200, 'development', 'stub'))
        order = self.command(order, 'assign', 'demo-dispatcher', assigneeId='technician-1')
        order = self.command(order, 'start', 'demo-technician')
        order = self.wait_status(order, 'IN_PROGRESS')
        order = self.command(order, 'complete', 'demo-technician', resolution='恢复线路。')
        order = self.command(order, 'accept')
        order = self.wait_status(order, 'CLOSED')
        order = self.command(order, 'rate', rating=5, comment='已恢复。')
        self.assertEqual(order['rating'], 5)
        self.assertEqual(order['syncStatus'], 'SYNCED')
        self.assertNotIn('_blockRevision', order)

    def test_http_auth_visibility_validation_and_conflict(self):
        self.assertEqual(self.request('GET', '/work-orders', token=None)[0], 401)
        self.assertEqual(self.request('GET', '/work-orders', token='unknown')[0], 401)
        self.assertEqual(self.request('GET', '/technicians')[0], 403)
        self.assertEqual(self.request('GET', '/technicians', token='demo-dispatcher')[0], 200)
        order = self.create()
        path = '/work-orders/' + order['id']
        self.assertEqual(self.request('GET', path, token='demo-student-2')[0], 404)
        self.assertEqual(self.request('POST', path + '/assign', {
            'version': order['version'], 'assigneeId': 'technician-1'})[0], 403)
        assigned = self.command(order, 'assign', 'demo-dispatcher', assigneeId='technician-1')
        self.assertEqual(self.request('POST', path + '/cancel', {
            'version': order['version'], 'reason': '取消'})[0], 409)
        self.assertEqual(self.request('POST', path + '/cancel', {
            'version': assigned['version'], 'reason': '取消', 'actorId': 'spoof'})[0], 422)
        self.assertEqual(self.request('POST', '/work-orders', {'roomId': 'room-101',
            'title': ' ', 'description': '故障', 'category': 'other'}, key='invalid')[0], 422)
        self.assertEqual(self.request('POST', '/work-orders', {'roomId': 'room-101',
            'title': '故障', 'description': '故障', 'category': 'other'})[0], 422)


class DefaultModeTests(unittest.TestCase):
    def test_default_and_production_reject_demo_and_do_not_start_worker(self):
        for mode in ('unconfigured', 'production'):
            with self.subTest(mode=mode):
                server = Server(mode)
                try:
                    status, context = server.request('GET', '/api/m3/v1/context')
                    self.assertEqual((status, context['mode'], context['dependencyMode']),
                                     (200, mode, 'unavailable'))
                    status, error = server.request('GET', '/api/m3/v1/work-orders', token='demo-student')
                    self.assertEqual(status, 503)
                    self.assertEqual(error['code'], 'IDENTITY_UNAVAILABLE')
                    self.assertFalse(list(Path(server.temp.name).glob('*.db')))
                finally:
                    server.close()


if __name__ == '__main__':
    unittest.main()
